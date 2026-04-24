from app.clients.llm import LLMClient
from app.schemas.modules import ChatRequest, ChatResponse
from app.services.blast_radius import BlastRadiusService
from app.services.dead_data import DeadDataService
from app.services.passport import DataPassportService
from app.services.storm_warning import get_storm_warning_service


class ChatService:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.dead_data = DeadDataService()
        self.passport = DataPassportService()
        self.storm = get_storm_warning_service()
        self.blast = BlastRadiusService()

    async def reply(self, payload: ChatRequest) -> ChatResponse:
        from app.services.mcp_agent import get_mcp_agent
        
        try:
            # --- DEMO MOCK INJECTION FOR VIDEO RECORDING ---
            q = payload.question.lower()
            if "export" in q or "sheet" in q:
                import asyncio
                await asyncio.sleep(2.5)  # Simulate "agentic thinking" delay
                fake_ans = "I have extracted the dead data candidates and generated a cost-savings report.\n\n[📊 View your Google Sheet](https://docs.google.com/spreadsheets/d/1a-RPfc16qIuwwKTMqoSvOi4nCr6pntgcs3OkVvj2W6Q/edit)"
                
                # Seed the mock into the agent's memory so future LLM queries know about it
                agent = await get_mcp_agent()
                session_id = payload.session_id or "default"
                if session_id not in agent.history:
                    agent.history[session_id] = []
                # Don't add user query here because mcp_agent run_loop does it, but since we bypass it, we must add both
                agent.history[session_id].append({"role": "user", "content": payload.question})
                agent.history[session_id].append({"role": "assistant", "content": fake_ans})
                
                return ChatResponse(module="mcp-orchestrator", answer=fake_ans, context_summary="MCP Orchestration Hub active")
            # -----------------------------------------------

            agent = await get_mcp_agent()
            # Pass the session_id from the payload down to the agentic loop
            session_id = payload.session_id or "default"
            answer = await agent.run_loop(payload.question, session_id=session_id, entity_id=payload.entity_id)
            return ChatResponse(module="mcp-orchestrator", answer=answer, context_summary="MCP Orchestration Hub active")
        except Exception as e:
            error_msg = str(e)
            if "rate_limit_exceeded" in error_msg.lower():
                user_msg = "MetaGuard is currently at maximum capacity (Groq Rate Limit). Please try again in a few minutes."
            else:
                user_msg = f"MetaGuard Orchestrator error: {error_msg}"
            return ChatResponse(module="mcp-orchestrator", answer=user_msg, context_summary="Error State")

    def _extract_module(self, question: str) -> tuple[str, str]:
        normalized = question.strip()
        prefixes = {
            "in dead data:": "dead-data",
            "in passport:": "passport",
            "in storm:": "storm",
            "in blast:": "blast",
        }
        lower = normalized.lower()
        for prefix, module in prefixes.items():
            if lower.startswith(prefix):
                return module, normalized[len(prefix):].strip()
        return "general", normalized

    def _build_context(self, module: str, question: str, entity_id: str | None) -> str:
        if module == "dead-data":
            scan = self.dead_data.scan()
            top = scan.assets[0] if scan.assets else None
            if top is None:
                return "No dead-data findings are available."
            return (
                f"Selected entity: {entity_id or 'not provided'}.\n"
                f"Top flagged asset: {top.fqn}.\n"
                f"Category: {top.category}. Monthly cost: {top.monthly_cost_estimate}. "
                f"Safe to delete: {top.safe_to_delete}."
            )
        if module == "passport" and entity_id:
            passport = self.passport.get_passport(entity_id)
            return (
                f"Asset: {entity_id}\n"
                f"Trust score: {passport.trust_score.total}\n"
                f"Summary: {passport.summary}\n"
                f"Lineage: {passport.sections.get('lineage_story', 'Not available')}\n"
                f"Issues: {passport.sections.get('known_issues', 'None')}"
            )
        if module == "storm":
            alerts = self.storm.list_alerts().alerts
            latest = alerts[0] if alerts else None
            return (
                f"Active alerts: {len(alerts)}.\n"
                f"Latest alert: {latest.summary if latest else 'none'}.\n"
                f"Latest severity: {latest.severity if latest else 'none'}."
            )
        if module == "blast" and entity_id:
            report = self.blast.get_table_report(entity_id)
            top_nodes = ", ".join(node.fqn for node in report.nodes[:3]) if report.nodes else "None"
            return (
                f"Entity: {entity_id}\n"
                f"Overall blast risk: {report.overall_risk_score}\n"
                f"Impacted assets: {report.total_impacted_assets}\n"
                f"Top downstream consumers: {top_nodes}"
            )
        return f"Entity: {entity_id or 'not provided'}.\nQuestion: {question}"
