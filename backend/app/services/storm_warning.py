from __future__ import annotations

import asyncio
import random
from functools import lru_cache
from uuid import uuid4

from app.clients.llm import LLMClient
from app.clients.openmetadata import _hash_columns, get_openmetadata_client
from app.core.config import get_settings
from app.core.utils import utc_now
from app.services.impact import get_impact_scorer
from app.schemas.modules import (
    AlertConsumer,
    DiagnosticSignal,
    SchemaChange,
    StormAlert,
    StormAlertsResponse,
    StormSimulationRequest,
    WatchedAsset,
    WatchedAssetsResponse,
)
from app.services.passport_support import get_passport_support_service


class StormWarningService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = get_openmetadata_client()
        self.llm = LLMClient()
        self.passport_support = get_passport_support_service()
        self.watched_assets = {
            fqn: versions[-1]["hash"]
            for fqn, versions in self.client.schema_versions.items()
            if versions
        }
        self.alerts: list[StormAlert] = []
        self._watch_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Seed initial demo state if in mock mode
        if not self.settings.app_mode.lower() == "live":
            self._seed_mock_alerts()

    def list_alerts(self) -> StormAlertsResponse:
        alerts = sorted(self.alerts, key=lambda alert: (-alert.impact_score, alert.created_at))
        return StormAlertsResponse(total=len(alerts), alerts=alerts)

    def get_alert(self, alert_id: str) -> StormAlert:
        for alert in self.alerts:
            if alert.id == alert_id:
                return alert
        raise KeyError(f"Alert '{alert_id}' was not found.")

    def simulate(self, payload: StormSimulationRequest) -> StormAlert:
        version = self.client.apply_schema_change(payload.fqn, [change.model_dump() for change in payload.changes])
        self.watched_assets[payload.fqn] = version["hash"]
        severity = self._classify_severity(payload.changes)
        return self._build_alert(payload.fqn, payload.changes, severity)

    def watched(self) -> WatchedAssetsResponse:
        assets = [
            WatchedAsset(fqn=fqn, asset_type=self.client.get_asset_type(fqn), last_version_hash=version_hash)
            for fqn, version_hash in sorted(self.watched_assets.items())
        ]
        return WatchedAssetsResponse(watched_assets=assets)

    async def start_watcher(self) -> None:
        if self._watch_task and not self._watch_task.done():
            return
        self._stop_event = asyncio.Event()
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def stop_watcher(self) -> None:
        self._stop_event.set()
        if self._watch_task is not None:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

    async def poll_once(self) -> list[StormAlert]:
        alerts: list[StormAlert] = []
        for fqn in list(self.watched_assets):
            try:
                new_alert = self._check_asset_for_change(fqn)
            except Exception:
                continue
            if new_alert is not None:
                alerts.append(new_alert)
        return alerts

    def _classify_severity(self, changes: list[SchemaChange]) -> str:
        severity = "info"
        for change in changes:
            if change.change_type in {"drop_column", "rename_column"}:
                return "critical"
            if change.change_type == "type_change" and change.before and change.after:
                severity = "high" if self._is_narrowed_type(change.before, change.after) else "medium"
            elif change.change_type == "null_spike":
                severity = "high"
            elif change.change_type == "freshness_delay":
                severity = "medium"
            elif change.change_type == "add_column" and severity == "info":
                severity = "low"
        return severity

    def _trace_downstream(self, fqn: str) -> list[AlertConsumer]:
        lineage = self.client.get_lineage(fqn, depth=10)
        return [
            AlertConsumer(
                fqn=node["fqn"],
                entity_type=node["entity_type"],
                owner=(self.client.get_owner(node["fqn"]) or {}).get("name"),
                next_run_time="Unknown",
                shortest_path=node["path"],
            )
            for node in lineage["downstream"]
        ]

    def _is_narrowed_type(self, before: str, after: str) -> bool:
        order = {"STRING": 5, "FLOAT": 4, "BIGINT": 3, "INT": 2}
        return order.get(after, 10) < order.get(before, 10)

    async def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            await self.poll_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.settings.poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

    def _check_asset_for_change(self, fqn: str) -> StormAlert | None:
        table = self.client.get_table(fqn)
        columns = table.get("columns", [])
        new_hash = self.client.get_schema_versions(fqn)[-1]["hash"] if self.client.get_schema_versions(fqn) else None
        current_hash = _hash_columns(columns)
        if new_hash == current_hash or self.watched_assets.get(fqn) == current_hash:
            self.watched_assets[fqn] = current_hash
            return None

        previous_columns = {
            column["name"]: column.get("type")
            for column in self.client.get_schema_versions(fqn)[-1]["columns"]
        }
        current_columns = {column["name"]: column.get("type") for column in columns}
        changes = self._diff_columns(previous_columns, current_columns)
        self.client.schema_versions[fqn].append(
            {
                "version": len(self.client.schema_versions[fqn]) + 1,
                "captured_at": utc_now().isoformat(),
                "columns": [dict(name=name, type=col_type, description="") for name, col_type in current_columns.items()],
                "hash": current_hash,
            }
        )
        self.client.tables[fqn] = table
        self.watched_assets[fqn] = current_hash
        if not changes:
            return None
        severity = self._classify_severity(changes)
        return self._build_alert(fqn, changes, severity)

    def _diff_columns(self, previous: dict[str, str | None], current: dict[str, str | None]) -> list[SchemaChange]:
        changes: list[SchemaChange] = []
        for name, old_type in previous.items():
            if name not in current:
                changes.append(SchemaChange(column=name, change_type="drop_column", before=old_type, after=None))
            elif current[name] != old_type:
                changes.append(
                    SchemaChange(column=name, change_type="type_change", before=old_type, after=current[name])
                )
        for name, new_type in current.items():
            if name not in previous:
                changes.append(SchemaChange(column=name, change_type="add_column", before=None, after=new_type))
        return changes

    def _build_alert(self, fqn: str, changes: list[SchemaChange], severity: str) -> StormAlert:
        impacted = self._trace_downstream(fqn) if severity in {"critical", "high"} else []
        
        signals_list: list[DiagnosticSignal] = []
        for change in changes:
            if change.change_type == "drop_column":
                signals_list.append(DiagnosticSignal(code="SCHEMA_BREAK", label=f"Dropped Field: {change.column}", category="breaking", severity="critical", value=change.column))
            elif change.change_type == "type_change":
                signals_list.append(DiagnosticSignal(code="FORMAT_STORM", label=f"Type Drift: {change.column}", category="drift", severity="high", value={"before": change.before, "after": change.after}))
            elif change.change_type == "rename_column":
                signals_list.append(DiagnosticSignal(code="REF_FAIL", label=f"Renamed Field: {change.column}", category="breaking", severity="critical", value=change.column))
            elif change.change_type == "null_spike":
                signals_list.append(DiagnosticSignal(code="COMPLETENESS_DROP", label=f"Null Surge: {change.column}", category="quality", severity="high", value="92% increase"))
            elif change.change_type == "freshness_delay":
                signals_list.append(DiagnosticSignal(code="SLA_MISS", label=f"Freshness Delay: {change.column}", category="freshness", severity="medium", value="4.2h late"))
        
        if impacted:
            signals_list.append(DiagnosticSignal(code="IMPACT_CHAIN", label=f"{len(impacted)} Affected Consumers", category="lineage", severity="high", value=len(impacted)))

        summary = self.llm.generate(
            system_prompt=(
                "Write a single, high-impact sentence summarizing the schema event. "
                "Focus on 'What changed' and the immediate risk level. "
                "The summary must be under 22 words. "
                "Do not use markdown bold or bullets."
            ),
            user_content=(
                f"Asset: {fqn}\n"
                f"Severity: {severity}\n"
                f"Changes: {'; '.join(f'{change.change_type} {change.column}' for change in changes)}\n"
                f"Impacted consumers: {len(impacted)}\n"
                f"Top impacted consumer: {impacted[0].fqn if impacted else 'None'}"
            ),
            max_tokens=80,
        )
        alert = StormAlert(
            id=str(uuid4()),
            fqn=fqn,
            severity=severity,  # type: ignore[arg-type]
            summary=summary,
            change_count=len(changes),
            changes=changes,
            impacted_consumers=impacted,
            created_at=utc_now(),
            signals=signals_list,
        )
        
        impact_score, impact_reason = get_impact_scorer().calculate(fqn)
        # Add jitter for simulation variety (Demo Mode)
        impact_score = max(5.0, min(95.0, impact_score + random.uniform(-5.0, 5.0)))
        alert.impact_score = impact_score
        alert.impact_reason = impact_reason

        self.alerts.insert(0, alert)
        self.alerts = self.alerts[:50]
        self.passport_support.invalidate(fqn)
        return alert

    def _seed_mock_alerts(self) -> None:
        """Seed high-fidelity incidents for the Master Demo."""
        # Incident 1: Critical Schema Break on Finance Core
        self.simulate(StormSimulationRequest(
            fqn="warehouse.commerce.curated.fct_orders",
            changes=[SchemaChange(column="order_total", change_type="drop_column", before="FLOAT", after=None)]
        ))
        
        # Incident 2: Quality Drift on Customer 360
        self.simulate(StormSimulationRequest(
            fqn="warehouse.commerce.curated.customer_360",
            changes=[SchemaChange(column="source", change_type="null_spike", before="99% filled", after="8% filled")]
        ))
        
        # Incident 3: Freshness Miss on Revenue Mart
        self.simulate(StormSimulationRequest(
            fqn="warehouse.commerce.finance.finance_revenue_mart",
            changes=[SchemaChange(column="revenue", change_type="freshness_delay", before="6h lag", after="18h lag")]
        ))


@lru_cache
def get_storm_warning_service() -> StormWarningService:
    return StormWarningService()
