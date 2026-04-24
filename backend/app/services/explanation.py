import time
import json
import hashlib
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.clients.llm import LLMClient
from app.schemas.modules import (
    CauseTree,
    DiagnosticSignal,
    ExplanationResponse,
)
from app.services.dead_data import get_dead_data_service
from app.services.storm_warning import get_storm_warning_service
from app.services.impact import get_impact_scorer


class ExplanationService:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.dead_data = get_dead_data_service()
        self.storm = get_storm_warning_service()
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300 # 5 minutes

    async def explain(self, fqn: str) -> ExplanationResponse:
        signals = self._gather_signals(fqn)
        
        # Semantic Cache Lookup
        # We hash the signals code to ensure cache invalidates if data health changes
        signal_hash = hashlib.md5("".join(s.code for s in signals).encode()).hexdigest()
        cache_key = f"{fqn}:{signal_hash}"
        
        # bypass old cache during final refinement
        if False and cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() - entry['timestamp'] < self.cache_ttl:
                return entry['data']

        impact_score, impact_reason = get_impact_scorer().calculate(fqn)
        
        if not signals:
            resp = self._build_empty_explanation(fqn)
            resp.impact_score = impact_score
            resp.impact_reason = impact_reason
            return resp

        # Build technical tree
        tree = self._build_cause_tree(fqn, signals)

        narrative_data = self.llm.generate(
            system_prompt=(
                "You are the MetaGuard RCA Agent. Analyze the health signals for a data asset and produce aprofessional RCA report.\n\n"
                "CONTEXT CATEGORIES:\n"
                "1. LIVE INCIDENTS: Schema breaks, type drifts, quality spikes. Focus on 'Why this broke today'.\n"
                "2. DEAD DATA: Orphans, Zombies, Duplicates. Focus on 'Why this should be cleaned'.\n\n"
                "KEYWORD REQUIREMENTS FOR DEAD DATA:\n"
                "- If signals like DUPE_FINGERPRINT appear, explain 'Why it is a duplicate'.\n"
                "- If signals like ZOMBIE_OUTPUT appear, explain 'Why it is a zombie' (pipe writes to dead ends).\n"
                "- If an asset is safe to remove with high confidence, explain 'Why it is an immediate clean candidate'.\n\n"
                "STRUCTURE:\n"
                "TITLE: Concise headline\n"
                "NARRATIVE: 2 paragraphs explaining evidence chain and human impact.\n"
                "ROOT_CAUSE: One sentence identifying the primary failure point.\n"
                "ACTIONS: 3 short bullet points."
            ),
            user_content=(
                f"Asset: {fqn}\n"
                f"Signals: {'; '.join(f'[{s.code}: {s.label}]' for s in signals)}"
            ),
            max_tokens=600,
        )

        resp = self._parse_llm_narrative(fqn, signals, narrative_data, tree)
        resp.impact_score = impact_score
        resp.impact_reason = impact_reason
        
        # Commit to session cache
        self.cache[cache_key] = {'data': resp, 'timestamp': time.time()}
        return resp

    def _gather_signals(self, fqn: str) -> list[DiagnosticSignal]:
        # Check dead data signals
        dead_match = next((a for a in self.dead_data.scan().assets if a.fqn == fqn), None)
        if dead_match:
            return dead_match.signals

        # Check storm alerts
        storm_match = next((a for a in self.storm.alerts if a.fqn == fqn), None)
        if storm_match:
            return storm_match.signals

        return []

    def _build_cause_tree(self, fqn: str, signals: list[DiagnosticSignal]) -> CauseTree:
        # Simple hierarchical tree based on signal severity
        root = CauseTree(id=str(uuid4()), label=f"Anomaly: {fqn}")
        for signal in signals:
            child = CauseTree(id=str(uuid4()), label=signal.label, signal_code=signal.code)
            root.children.append(child)
        return root

    def _build_empty_explanation(self, fqn: str) -> ExplanationResponse:
        return ExplanationResponse(
            fqn=fqn,
            title="Evidence data has expired",
            narrative="No diagnostic signals are currently active for this asset. The anomaly may have been resolved or the logs rotated.",
            root_cause="Information unavailable.",
            severity="info",
            cause_tree=CauseTree(id="root", label="Trace expired"),
            suggested_actions=["Monitor for future drifts", "Check repository logs"],
        )

    def _parse_llm_narrative(
        self, fqn: str, signals: list[DiagnosticSignal], raw_text: str, tree: CauseTree
    ) -> ExplanationResponse:
        # Normalize text: strip markdown bolding and unify newlines
        clean_text = raw_text.replace("**", "").replace("###", "").replace("\r\n", "\n").strip()
        
        title = "Diagnostic Report"
        narrative = ""
        root_cause = "Pending verification."
        actions = []

        # 1. Extract Title
        if "TITLE:" in clean_text.upper():
            parts = clean_text.split("TITLE:", 1)[1].split("\n", 1)
            title = parts[0].strip()
            clean_text = parts[1] if len(parts) > 1 else ""

        # 2. Extract Narrative
        # Looking for NARRATIVE: or just the first big block
        if "NARRATIVE:" in clean_text.upper():
            parts = clean_text.split("NARRATIVE:", 1)[1].split("ROOT", 1)
            narrative = parts[0].strip()
            clean_text = "ROOT" + parts[1] if len(parts) > 1 else ""
        
        # 3. Extract Root Cause (Verdict)
        # Handle variations: ROOT_CAUSE:, ROOT CAUSE:, ROOT CAUSE ANALYSIS:
        search_text = clean_text.upper()
        root_marker = None
        for m in ["ROOT_CAUSE:", "ROOT CAUSE ANALYSIS:", "ROOT CAUSE:"]:
            if m in search_text:
                root_marker = m
                break
        
        if root_marker:
            parts = clean_text.split(root_marker, 1)[1].split("ACTIONS:", 1)
            root_cause = parts[0].strip()
            clean_text = "ACTIONS:" + parts[1] if len(parts) > 1 else ""

        # 4. Extract Actions
        if "ACTIONS:" in clean_text.upper():
            action_blob = clean_text.split("ACTIONS:", 1)[1]
            # Clean up individual lines, removing leading dots/dashes
            for line in action_blob.split("\n"):
                line = line.strip().lstrip(".-*•0123456789 ")
                if line and len(line) > 5:
                    actions.append(line)
        
        # Fallback if parsing failed
        if not narrative and not actions:
            # If no markers were found, the whole thing is the narrative
            narrative = raw_text.replace("**", "").strip()

        max_severity = "info"
        if signals:
            orders = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            max_severity = min(signals, key=lambda s: orders.get(s.severity, 4)).severity

        return ExplanationResponse(
            fqn=fqn,
            title=title,
            narrative=narrative.strip(),
            root_cause=root_cause.strip(),
            severity=max_severity,
            cause_tree=tree,
            suggested_actions=actions or ["No immediate action required."],
        )

        max_severity = "info"
        if signals:
            orders = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            max_severity = min(signals, key=lambda s: orders.get(s.severity, 4)).severity

        return ExplanationResponse(
            fqn=fqn,
            title=title,
            narrative=narrative.strip(),
            root_cause=root_cause,
            severity=max_severity,
            cause_tree=tree,
            suggested_actions=actions or ["No immediate action required."],
        )


_instance: ExplanationService | None = None


def get_explanation_service() -> ExplanationService:
    global _instance
    if _instance is None:
        _instance = ExplanationService()
    return _instance
