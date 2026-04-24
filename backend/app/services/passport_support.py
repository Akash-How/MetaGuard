from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

from app.clients.llm import LLMClient
from app.clients.openmetadata import get_openmetadata_client
from app.core.utils import utc_now
from app.schemas.modules import PassportMetadata, TrustScoreBreakdown


class PassportSupportService:
    def __init__(self) -> None:
        self.client = get_openmetadata_client()
        self.llm = LLMClient()
        self.cache: dict[str, tuple[object, dict[str, Any]]] = {}
        self.cache_ttl = timedelta(minutes=15)

    def aggregate_metadata(self, fqn: str) -> PassportMetadata:
        asset = self.client.get_asset(fqn)
        glossary: dict[str, str] = {}
        for column in asset.get("columns", []):
            glossary.update(self.client.get_glossary(column["name"]))
        return PassportMetadata(
            table=asset,
            quality=self.client.get_quality(fqn),
            lineage=self.client.get_lineage(fqn, depth=10),
            usage=self.client.get_usage(fqn),
            profiling=self.client.get_profiling(fqn),
            owner=self.client.get_owner(fqn),
            glossary=glossary,
        )

    def calculate_trust_score(self, metadata: PassportMetadata) -> TrustScoreBreakdown:
        quality_score = round((metadata.quality or {}).get("pass_rate", 0.0) * 40)
        freshness_hours = (metadata.profiling or {}).get("freshness_hours")
        if freshness_hours is None:
            freshness_score = 0
        elif freshness_hours <= 24:
            freshness_score = 25
        elif freshness_hours <= 72:
            freshness_score = 18
        elif freshness_hours <= 168:
            freshness_score = 10
        else:
            freshness_score = 2
        ownership_score = 15 if (metadata.owner or {}).get("active") else 0
        columns = metadata.table.get("columns", [])
        described_columns = sum(1 for column in columns if column.get("description"))
        documentation_ratio = described_columns / len(columns) if columns else 0.0
        documentation_score = round((0.5 if metadata.table.get("description") else 0.0 + 0.5 * documentation_ratio) * 10)
        lineage = metadata.lineage or {}
        has_upstream = bool(lineage.get("upstream"))
        has_downstream = bool(lineage.get("downstream"))
        lineage_score = 10 if has_upstream and has_downstream else 5 if has_upstream or has_downstream else 0
        total = quality_score + freshness_score + ownership_score + documentation_score + lineage_score
        return TrustScoreBreakdown(
            quality=quality_score,
            freshness=freshness_score,
            ownership=ownership_score,
            documentation=documentation_score,
            lineage=lineage_score,
            total=total,
        )

    def generate_sections(self, fqn: str, metadata: PassportMetadata) -> dict[str, str]:
        quality = metadata.quality or {}
        owner = metadata.owner or {}
        lineage = metadata.lineage or {}
        columns = metadata.table.get("columns", [])
        top_columns = columns[:8]
        quality_issues = quality.get("failing_tests") or []
        upstream = [node["fqn"] for node in lineage.get("upstream", [])[:3]]
        downstream = [node["fqn"] for node in lineage.get("downstream", [])[:3]]
        column_context = "\n".join(
            f"- {column['name']}: {metadata.glossary.get(column['name']) or column.get('description') or 'Definition pending.'}"
            for column in top_columns
        )

        # Consolidate into ONE LLM call for 2x speed
        intelligence = self.llm.generate(
            system_prompt=(
                "You are MetaGuard Intelligence. Summarize the data passport in two sections separated by '---'.\n"
                "Section 1 (Business): Exactly 4 short bullet points. Topic: business purpose, trust risk, downstream impact, action.\n"
                "Section 2 (Lineage): Exactly 4 short bullet points. Topic: upstream flow, downstream distribution, path complexity.\n"
                "Each bullet must be one simple sentence under 20 words. No markdown bold. "
                "Output ONLY the bullets, no section headers like 'Summary:' or 'Lineage:'."
            ),
            user_content=(
                f"Table: {metadata.table['display_name']}\n"
                f"Description: {metadata.table.get('description') or 'None'}\n"
                f"Owner: {owner.get('name', 'Unassigned')}\n"
                f"Upstream: {', '.join(upstream) if upstream else 'None'}\n"
                f"Downstream: {', '.join(downstream) if downstream else 'None'}\n"
                f"Issues: {', '.join(quality_issues) if quality_issues else 'None'}"
            ),
            model="",
            max_tokens=250,
        )

        parts = intelligence.split("---")
        business_part = parts[0].strip() if len(parts) > 0 else "Analysis pending."
        lineage_part = parts[1].strip() if len(parts) > 1 else "Lineage mapping in progress."

        sections = {
            "plain_english_summary": business_part,
            "lineage_story": lineage_part,
            "column_guide": column_context if column_context else "No columns defined.",
            "known_issues": "No known issues." if not quality_issues else "Known issues: " + "; ".join(quality_issues),
            "contact": f"Owner: {owner.get('name', 'Unassigned')}. Suggested message: Hi, I have a question about {fqn}.",
        }
        if len(columns) > 8:
            sections["column_guide"] += f"\n+ {len(columns) - 8} more columns"
        return sections

    def cache_get(self, fqn: str) -> dict[str, Any] | None:
        cached = self.cache.get(fqn)
        if cached is None:
            return None
        created_at, payload = cached
        if utc_now() - created_at > self.cache_ttl:
            self.cache.pop(fqn, None)
            return None
        return payload

    def cache_set(self, fqn: str, payload: dict[str, Any]) -> None:
        self.cache[fqn] = (utc_now(), payload)

    def invalidate(self, fqn: str) -> None:
        self.cache.pop(fqn, None)


@lru_cache
def get_passport_support_service() -> PassportSupportService:
    return PassportSupportService()
