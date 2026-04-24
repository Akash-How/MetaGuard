from __future__ import annotations

from collections import Counter
from typing import Any

from app.clients.openmetadata import NOW, get_openmetadata_client
from app.core.utils import days_between, utc_now
from app.services.impact import get_impact_scorer
from app.schemas.modules import (
    DeadDataAssetDetail,
    DeadDataDependency,
    DeadDataItem,
    DeadDataScanResponse,
    DeadDataSummaryResponse,
    DeadDataValidationResponse,
    DiagnosticSignal,
)


class DeadDataService:
    def __init__(self) -> None:
        self.client = get_openmetadata_client()
        self.cost_per_gb_month = 0.023
        self.removed_assets: set[str] = set()
        self.reviewed_assets: set[str] = set()

    def scan(self) -> DeadDataScanResponse:
        tables = self.client.list_all_tables()
        pipelines = self.client.list_all_pipelines()
        assets = [*tables, *pipelines]
        pipeline_fqns = {pipeline["fqn"] for pipeline in pipelines}
        duplicate_targets = self._build_duplicate_targets(tables)
        findings = [
            item
            for asset in assets
            if asset["fqn"] not in self.removed_assets
            if (item := self._classify_asset(asset, pipeline_fqns=pipeline_fqns, duplicate_targets=duplicate_targets)) is not None
        ]
        findings.sort(key=lambda item: (-item.impact_score, -(item.monthly_cost_estimate or 0.0)))
        return DeadDataScanResponse(generated_at=utc_now(), total_candidates=len(findings), assets=findings)

    def get_asset_detail(self, fqn: str) -> DeadDataAssetDetail:
        raw_signals = self._build_signals(fqn)
        item = self._classify_asset(raw_signals["asset"])
        if item is None:
            raise KeyError(f"Asset '{fqn}' is not currently classified as dead data.")
        return DeadDataAssetDetail(item=item, raw_signals=raw_signals)

    def validate(self, fqn: str) -> DeadDataValidationResponse:
        if fqn in self.removed_assets:
            return DeadDataValidationResponse(
                fqn=fqn,
                safe_to_delete=True,
                review_required=False,
                dependencies=[],
                rationale=["Asset has already been removed from the active dead-data queue."],
            )
        lineage = self.client.get_lineage(fqn, depth=5)
        return self._validation_from_lineage(fqn, lineage)

    def mark_removed(self, fqn: str) -> dict[str, str]:
        validation = self.validate(fqn)
        if not validation.safe_to_delete:
            raise ValueError("Asset cannot be removed because dependencies still require review.")
        self.removed_assets.add(fqn)
        self.reviewed_assets.discard(fqn)
        return {
            "fqn": fqn,
            "action": "removed",
            "message": "Asset removed from the active dead-data queue.",
        }

    def mark_reviewed(self, fqn: str) -> dict[str, str]:
        self.reviewed_assets.add(fqn)
        return {
            "fqn": fqn,
            "action": "reviewed",
            "message": "Asset marked as reviewed and acknowledged by the operator.",
        }

    def _validation_from_lineage(self, fqn: str, lineage: dict[str, Any]) -> DeadDataValidationResponse:
        dependencies = [
            DeadDataDependency(fqn=node["fqn"], reason="Downstream lineage dependency")
            for node in lineage["downstream"]
        ]
        rationale: list[str] = []
        safe_to_delete = True
        if dependencies:
            safe_to_delete = False
            rationale.append("Downstream lineage dependencies were found.")
        if self.client.is_quality_suite_active(fqn):
            safe_to_delete = False
            dependencies.append(DeadDataDependency(fqn=fqn, reason="Active quality suite references this asset"))
            rationale.append("Asset is still referenced by an active quality suite.")
        if not rationale:
            rationale.append("No downstream dependencies or quality suite references were found.")
        return DeadDataValidationResponse(
            fqn=fqn,
            safe_to_delete=safe_to_delete,
            review_required=not safe_to_delete,
            dependencies=dependencies,
            rationale=rationale,
        )

    def get_summary(self) -> DeadDataSummaryResponse:
        scan = self.scan()
        categories = Counter(item.category for item in scan.assets)
        return DeadDataSummaryResponse(
            total_monthly_waste=round(sum(item.monthly_cost_estimate or 0.0 for item in scan.assets), 2),
            category_breakdown=dict(categories),
            safe_to_delete_count=sum(1 for item in scan.assets if item.safe_to_delete),
            review_required_count=sum(1 for item in scan.assets if item.review_required),
        )

    def _classify_asset(
        self,
        asset: dict[str, Any],
        *,
        pipeline_fqns: set[str],
        duplicate_targets: dict[str, str],
    ) -> DeadDataItem | None:
        signals = self._build_signals(asset["fqn"], preloaded_asset=asset)
        asset_type = "pipeline" if asset["fqn"] in pipeline_fqns else "table"
        validation = self._validation_from_lineage(asset["fqn"], signals["lineage"])
        owner = signals["owner"]
        usage = signals["usage"]
        profiling = signals["profiling"] or {}
        lineage = signals["lineage"]
        notes: list[str] = []
        category: str | None = None
        confidence = "medium"

        owner_inactive = owner is None or not owner.get("active")
        zero_queries_90d = usage.get("query_count_90d", 0) == 0
        zero_queries_60d = usage.get("query_count_60d", 0) == 0
        no_consumers = len(lineage.get("downstream", [])) == 0

        signals_list: list[DiagnosticSignal] = []
        if asset_type == "table":
            duplicate_target = duplicate_targets.get(asset["fqn"])
            stale_days = days_between(profiling.get("last_row_added_at"), NOW)
            
            if duplicate_target and owner and owner.get("active"):
                category = "duplicate"
                signals_list.append(DiagnosticSignal(code="DUPE_FINGERPRINT", label="Identical Column Signature", category="structural", severity="high", value=duplicate_target))
                notes.append(f"Column fingerprint matches {duplicate_target}.")
                confidence = "high"
            elif owner_inactive and zero_queries_90d and no_consumers:
                category = "orphan"
                signals_list.append(DiagnosticSignal(code="INACTIVE_OWNER", label="Owner Inactive", category="ownership", severity="high"))
                signals_list.append(DiagnosticSignal(code="ZERO_QUERIES_90D", label="No Usage (90d)", category="usage", severity="medium"))
                signals_list.append(DiagnosticSignal(code="NO_DOWNSTREAM", label="No Downstream Consumers", category="lineage", severity="low"))
                notes.append("No active owner, no recent queries, and no downstream consumers.")
                confidence = "high"
            elif zero_queries_60d and stale_days is not None and stale_days >= 90:
                category = "stale"
                signals_list.append(DiagnosticSignal(code="STALE_DATA", label="No New Rows (90d+)", category="freshness", severity="medium", value=stale_days))
                signals_list.append(DiagnosticSignal(code="ZERO_QUERIES_60D", label="No Usage (60d)", category="usage", severity="medium"))
                notes.append("No new rows for 90+ days and no recent queries.")
                confidence = "medium"
        else:
            writes_to = asset.get("writes_to", [])
            zombie_tables = [target for target in writes_to if len(self.client.get_lineage(target, depth=3)["downstream"]) == 0]
            if asset.get("active") and zombie_tables and zero_queries_60d:
                category = "zombie"
                signals_list.append(DiagnosticSignal(code="ZOMBIE_OUTPUT", label="Pipe Writes to Dead Ends", category="lineage", severity="high", value=zombie_tables))
                signals_list.append(DiagnosticSignal(code="ZERO_QUERIES_60D", label="No Usage (60d)", category="usage", severity="medium"))
                notes.append(f"Pipeline writes to low-value asset(s): {', '.join(zombie_tables)}.")
                confidence = "high"

        if category is None:
            return None

        if lineage.get("coverage") == "partial":
            notes.append("Lineage coverage is partial. Manual confirmation recommended.")
            signals_list.append(DiagnosticSignal(code="PARTIAL_LINEAGE", label="Low Lineage Confidence", category="lineage", severity="info"))
        
        if asset["fqn"] in self.reviewed_assets:
            notes.append("This asset was already reviewed by the operator.")
        
        impact_score, impact_reason = get_impact_scorer().calculate(asset["fqn"])

        return DeadDataItem(
            fqn=asset["fqn"],
            asset_type=asset_type,
            category=category,
            owner=owner["name"] if owner else None,
            team=owner["team"] if owner else None,
            monthly_cost_estimate=self._estimate_monthly_cost(asset["fqn"], asset_type, asset),
            confidence=confidence,
            safe_to_delete=validation.safe_to_delete,
            review_required=validation.review_required,
            notes=notes,
            signals=signals_list,
            impact_score=impact_score,
            impact_reason=impact_reason,
        )

    def _estimate_monthly_cost(self, fqn: str, asset_type: str, asset: dict[str, Any]) -> float | None:
        if asset_type == "pipeline":
            return round(asset.get("avg_run_duration_hours", 0) * 12.0, 2)
        profiling = self.client.get_profiling(fqn)
        if profiling is None:
            return None
        gb_size = profiling["byte_size"] / (1024**3)
        return round(gb_size * self.cost_per_gb_month, 2)

    def _build_duplicate_targets(self, tables: list[dict[str, Any]]) -> dict[str, str]:
        fingerprints: dict[tuple[tuple[str, str], ...], list[str]] = {}
        for table in tables:
            fingerprint = tuple(sorted((column["name"], column["type"]) for column in table.get("columns", [])))
            fingerprints.setdefault(fingerprint, []).append(table["fqn"])

        duplicates: dict[str, str] = {}
        for fqns in fingerprints.values():
            if len(fqns) < 2:
                continue
            anchor = sorted(fqns)[0]
            for fqn in fqns:
                if fqn != anchor:
                    duplicates[fqn] = anchor
        return duplicates

    def _build_signals(self, fqn: str, preloaded_asset: dict[str, Any] | None = None) -> dict[str, Any]:
        asset = preloaded_asset
        if asset is None:
            tables = {table["fqn"] for table in self.client.list_all_tables()}
            if fqn in tables:
                asset = self.client.get_table(fqn)
            else:
                asset = next(pipeline for pipeline in self.client.list_all_pipelines() if pipeline["fqn"] == fqn)
        asset_type = "pipeline" if fqn in {pipeline["fqn"] for pipeline in self.client.list_all_pipelines()} else "table"
        return {
            "asset": asset,
            "usage": self.client.get_usage(fqn),
            "profiling": None if asset_type == "pipeline" else self.client.get_profiling(fqn),
            "lineage": self.client.get_lineage(fqn, depth=5),
            "owner": self.client.get_owner(fqn),
            "quality": {"pass_rate": 1.0, "failing_tests": []} if asset_type == "pipeline" else self.client.get_quality(fqn),
            "schema_versions": [] if asset_type == "pipeline" else self.client.get_schema_versions(fqn),
        }


_instance: DeadDataService | None = None


def get_dead_data_service() -> DeadDataService:
    global _instance
    if _instance is None:
        _instance = DeadDataService()
    return _instance
