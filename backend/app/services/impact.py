from __future__ import annotations

import math
from typing import Any

from app.clients.openmetadata import get_openmetadata_client


class ImpactScorer:
    def __init__(self) -> None:
        self.client = get_openmetadata_client()

    def calculate(self, fqn: str) -> tuple[float, str]:
        """
        Calculate a multi-dimensional impact score (0-100).
        Returns (score, reason)
        """
        # 1. Blast Radius (Lineage Depth/Breadth) - 40%
        lineage = self.client.get_lineage(fqn, depth=5)
        consumers = lineage.get("downstream", [])
        consumer_count = len(consumers)
        
        # Logarithmic scaling: 0=0, 1=10, 3=20, 7=30, 15+=40
        blast_score = min(math.log2(consumer_count + 1) * 10, 40.0)

        # 2. Active Friction (Usage) - 40%
        # OpenMetadata demo data supplies 90d and 60d counts. Approximate 30d usage:
        usage = self.client.get_usage(fqn)
        queries = usage.get("query_count_90d", 0) / 3.0
        # Scale: 0=0, 800+=40 (Ensuring variance for high-usage assets)
        usage_score = min((queries / 800.0) * 40.0, 40.0)

        # 3. Criticality Tier (Environment/Naming) - 20%
        tier_score = 5.0
        env = "sandbox"
        
        fqn_lower = fqn.lower()
        if "prod" in fqn_lower or "curated" in fqn_lower:
            tier_score = 20.0
            env = "production"
        elif "finance" in fqn_lower or "sales" in fqn_lower:
            tier_score = 15.0
            env = "business-critical"
        elif "stg" in fqn_lower or "raw" in fqn_lower:
            tier_score = 10.0
            env = "staging"

        total_score = round(blast_score + usage_score + tier_score, 1)

        # Build human-readable reason
        reasons = []
        if blast_score >= 30:
            reasons.append(f"impacts {consumer_count} downstream consumers")
        if usage_score >= 15:
            reasons.append(f"has high active friction (~{int(queries)} queries/mo)")
        if tier_score >= 15:
            reasons.append(f"is a {env} asset")

        if not reasons:
            reason = "Limited operational impact detected."
        else:
            reason = f"Critical because this {'; '.join(reasons)}."

        return total_score, reason


_instance: ImpactScorer | None = None


def get_impact_scorer() -> ImpactScorer:
    global _instance
    if _instance is None:
        _instance = ImpactScorer()
    return _instance
