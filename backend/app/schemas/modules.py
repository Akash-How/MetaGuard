from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeadDataDependency(BaseModel):
    fqn: str
    reason: str


class DiagnosticSignal(BaseModel):
    code: str
    label: str
    category: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    value: Any = None
    captured_at: datetime = Field(default_factory=datetime.now)


class DeadDataItem(BaseModel):
    fqn: str
    asset_type: Literal["table", "pipeline"]
    category: Literal["orphan", "zombie", "duplicate", "stale"]
    owner: str | None = None
    team: str | None = None
    monthly_cost_estimate: float | None = None
    confidence: Literal["low", "medium", "high"]
    safe_to_delete: bool
    review_required: bool
    notes: list[str] = Field(default_factory=list)
    signals: list[DiagnosticSignal] = Field(default_factory=list)
    impact_score: float = 0.0
    impact_reason: str = ""


class DeadDataScanResponse(BaseModel):
    status: str = "ok"
    generated_at: datetime
    total_candidates: int
    assets: list[DeadDataItem]


class DeadDataAssetDetail(BaseModel):
    status: str = "ok"
    item: DeadDataItem
    raw_signals: dict[str, Any]


class DeadDataValidationResponse(BaseModel):
    status: str = "ok"
    fqn: str
    safe_to_delete: bool
    review_required: bool
    dependencies: list[DeadDataDependency] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class DeadDataSummaryResponse(BaseModel):
    status: str = "ok"
    total_monthly_waste: float
    category_breakdown: dict[str, int]
    safe_to_delete_count: int
    review_required_count: int


class DeadDataActionResponse(BaseModel):
    status: str = "ok"
    fqn: str
    action: Literal["removed", "reviewed"]
    message: str


class TrustScoreBreakdown(BaseModel):
    quality: int
    freshness: int
    ownership: int
    documentation: int
    lineage: int
    total: int


class PassportMetadata(BaseModel):
    table: dict[str, Any]
    quality: dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    profiling: dict[str, Any] | None = None
    owner: dict[str, Any] | None = None
    glossary: dict[str, str] = Field(default_factory=dict)


class DataPassportResponse(BaseModel):
    status: str = "ok"
    fqn: str
    trust_score: TrustScoreBreakdown
    summary: str
    sections: dict[str, str]
    metadata: PassportMetadata
    cached: bool = False
    impact_score: float = 0.0
    impact_reason: str = ""


class PassportMcpRequest(BaseModel):
    question: str
    fqn: str


class PassportTrustScoreResponse(BaseModel):
    status: str = "ok"
    fqn: str
    trust_score: TrustScoreBreakdown


class SchemaChange(BaseModel):
    column: str
    change_type: str
    before: str | None = None
    after: str | None = None


class AlertConsumer(BaseModel):
    fqn: str
    entity_type: str
    owner: str | None = None
    next_run_time: str | None = None
    shortest_path: list[str] = Field(default_factory=list)


class CauseTree(BaseModel):
    id: str
    label: str
    signal_code: str | None = None
    children: list["CauseTree"] = Field(default_factory=list)


class ExplanationResponse(BaseModel):
    status: str = "ok"
    fqn: str
    title: str
    narrative: str
    root_cause: str
    severity: str
    cause_tree: CauseTree
    suggested_actions: list[str] = Field(default_factory=list)
    impact_score: float = 0.0
    impact_reason: str = ""


class StormAlert(BaseModel):
    id: str
    fqn: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    summary: str
    change_count: int
    changes: list[SchemaChange]
    impacted_consumers: list[AlertConsumer]
    created_at: datetime
    signals: list[DiagnosticSignal] = Field(default_factory=list)
    impact_score: float = 0.0
    impact_reason: str = ""


class StormAlertsResponse(BaseModel):
    status: str = "ok"
    total: int
    alerts: list[StormAlert]


class StormSimulationRequest(BaseModel):
    fqn: str
    changes: list[SchemaChange]


class WatchedAsset(BaseModel):
    fqn: str
    asset_type: str
    last_version_hash: str


class WatchedAssetsResponse(BaseModel):
    status: str = "ok"
    watched_assets: list[WatchedAsset]


class BlastRadiusNode(BaseModel):
    fqn: str
    entity_type: str
    hop_count: int
    owner: str | None = None
    usage_score: int
    quality_score: int
    risk_score: int
    impact_tier: Literal["direct", "indirect", "potential", "monitoring"]
    shortest_path: list[str]


class BlastRadiusReport(BaseModel):
    status: str = "ok"
    entity_type: Literal["table", "column"]
    target_fqn: str
    column_name: str | None = None
    overall_risk_score: int
    total_impacted_assets: int
    warnings: list[str] = Field(default_factory=list)
    nodes: list[BlastRadiusNode]


class BlastRadiusRequest(BaseModel):
    entity_id: str
    proposed_change: str


class RiskScoreResponse(BaseModel):
    status: str = "ok"
    fqn: str
    risk_score: int


class ChatRequest(BaseModel):
    question: str
    entity_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    status: str = "ok"
    module: str
    answer: str
    context_summary: str
