from app.clients.openmetadata import get_openmetadata_client
from app.schemas.modules import BlastRadiusNode, BlastRadiusReport, BlastRadiusRequest, RiskScoreResponse


class BlastRadiusService:
    def __init__(self) -> None:
        self.client = get_openmetadata_client()

    def analyze(self, payload: BlastRadiusRequest) -> BlastRadiusReport:
        return self.get_table_report(payload.entity_id)

    def get_table_report(self, fqn: str) -> BlastRadiusReport:
        lineage = self.client.get_lineage(fqn, depth=10)
        nodes = self._score_nodes(lineage["downstream"])
        warnings = [] if nodes else ["No downstream consumers."]
        if lineage.get("coverage") == "partial":
            warnings.append("Lineage coverage is partial.")
        overall_score = round(min(100, sum(node.risk_score for node in nodes) / max(len(nodes), 1))) if nodes else 0
        return BlastRadiusReport(
            entity_type="table",
            target_fqn=fqn,
            overall_risk_score=overall_score,
            total_impacted_assets=len(nodes),
            warnings=warnings,
            nodes=nodes[:20],
        )

    def get_column_report(self, fqn: str, column: str) -> BlastRadiusReport:
        direct_targets = self.client.column_lineage.get((fqn, column))
        if direct_targets is None:
            report = self.get_table_report(fqn)
            return report.model_copy(
                update={
                    "entity_type": "column",
                    "column_name": column,
                    "warnings": ["Column lineage not available - showing table-level impact.", *report.warnings],
                }
            )
        nodes = self._score_nodes(
            [
                {"fqn": target, "entity_type": self.client.get_asset_type(target), "hop_count": 1, "path": [fqn, target]}
                for target in direct_targets
            ]
        )
        return BlastRadiusReport(
            entity_type="column",
            target_fqn=fqn,
            column_name=column,
            overall_risk_score=round(min(100, sum(node.risk_score for node in nodes))),
            total_impacted_assets=len(nodes),
            warnings=[],
            nodes=nodes,
        )

    def get_risk_score(self, fqn: str) -> RiskScoreResponse:
        report = self.get_table_report(fqn)
        return RiskScoreResponse(fqn=fqn, risk_score=report.overall_risk_score)

    def _score_nodes(self, nodes: list[dict[str, object]]) -> list[BlastRadiusNode]:
        scored: list[BlastRadiusNode] = []
        seen: set[str] = set()
        for node in nodes:
            fqn = str(node["fqn"])
            if fqn in seen:
                continue
            seen.add(fqn)
            usage = self.client.get_usage(fqn)
            quality = self.client.get_quality(fqn)
            hop_count = int(node["hop_count"])
            usage_points = min(40, usage.get("query_count_90d", 0) // 50)
            proximity_points = max(10, 40 - (hop_count - 1) * 8)
            fragility_points = round((1 - quality.get("pass_rate", 1.0)) * 20)
            entity_type = str(node["entity_type"])
            if entity_type == "dashboard":
                tier = "monitoring"
            elif hop_count == 1:
                tier = "direct"
            elif hop_count <= 4:
                tier = "indirect"
            else:
                tier = "potential"
            scored.append(
                BlastRadiusNode(
                    fqn=fqn,
                    entity_type=entity_type,
                    hop_count=hop_count,
                    owner=(self.client.get_owner(fqn) or {}).get("name"),
                    usage_score=usage_points,
                    quality_score=fragility_points,
                    risk_score=min(100, usage_points + proximity_points + fragility_points),
                    impact_tier=tier,
                    shortest_path=list(node["path"]),
                )
            )
        scored.sort(key=lambda item: item.risk_score, reverse=True)
        return scored
