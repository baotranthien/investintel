from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any

from sqlalchemy.orm import Session
from pydantic import ValidationError

from .gateway import AIGateway
from .prompt_registry import PROMPT_VERSION, SYSTEM_PROMPT, build_chat_prompt
from .provider import AIProvider
from .providers import AIProviderError, OllamaProvider
from .router import AIRouter, TaskType
from .schemas import AIAnswerDraft, AIChatResponse, AICitation, AIClaim
from .tools import AITools


_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d[\d,]*(?:\.\d+)?%?")


def _numeric_values(value: str) -> set[Decimal]:
    found = set()
    for match in _NUMBER.findall(value):
        try:
            number = match.rstrip("%").replace(",", "")
            found.add(Decimal(number).normalize())
        except InvalidOperation:
            continue
    return found


class AIAnalyst:
    def __init__(self, provider: AIProvider | None = None, router: AIRouter | None = None):
        self.provider = provider or AIGateway()
        self.router = router or AIRouter()

    def _citations(self, context: dict[str, Any]) -> list[AICitation]:
        citations = []
        for index, item in enumerate(context.get("evidence", []), start=1):
            citations.append(AICitation(
                id=f"E{index:03d}",
                claim_type=item.get("claim_type", "UNCERTAINTY"),
                responsible_module=item.get("responsible_module", "unknown"),
                metric=item.get("metric"),
                value=item.get("value"),
                unit=item.get("unit"),
                source=item.get("source"),
                source_url=item.get("source_url"),
                observation_date=str(item["observation_date"]) if item.get("observation_date") else None,
                publication_date=str(item["publication_date"]) if item.get("publication_date") else None,
                retrieved_at=str(item["retrieved_at"]) if item.get("retrieved_at") else None,
                data_origin=item.get("data_origin"),
                freshness=item.get("freshness"),
                note=item.get("note"),
            ))
        return citations

    @staticmethod
    def _has_verifiable_evidence(citations: list[AICitation]) -> bool:
        return any(
            item.claim_type in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
            and bool(item.source)
            and item.data_origin not in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
            and item.freshness not in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
            for item in citations
        )

    @staticmethod
    def _has_supported_horizon(context: dict[str, Any]) -> bool:
        for tool in context.get("tools", []):
            data = tool.get("data")
            if not isinstance(data, dict):
                continue
            if data.get("horizon"):
                return True
            portfolio = data.get("portfolio")
            if isinstance(portfolio, dict) and any(
                holding.get("horizon")
                for holding in portfolio.get("holdings", [])
                if isinstance(holding, dict)
            ):
                return True
        return False

    def _insufficient_response(
        self,
        *,
        symbol: str | None,
        as_of: date,
        citations: list[AICitation],
        tools_used: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return AIChatResponse(
            status="INSUFFICIENT_DATA",
            symbol=symbol,
            as_of_date=as_of,
            prompt_version=PROMPT_VERSION,
            model=None,
            answer="Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.",
            claims=[AIClaim(claim_type="UNCERTAINTY", text=reason)],
            citations=citations,
            uncertainty=[reason],
            tools_used=tools_used,
            usage={},
        ).model_dump(mode="json")

    async def answer_question(
        self,
        question: str,
        *,
        session: Session,
        symbol: str | None = None,
        as_of: date | None = None,
        tool_names: list[str] | None = None,
        task_type: TaskType = "USER_CHAT",
    ) -> dict[str, Any]:
        requested_date = as_of or date.today()
        context = AITools.get_context(symbol, requested_date, tool_names, session)
        citations = self._citations(context)
        used_tools = [item["name"] for item in context.get("tools", [])]
        asks_horizon = any(term in question.casefold() for term in (
            "horizon", "investment period", "time horizon", "thời hạn", "kỳ hạn", "đầu tư bao lâu",
        ))
        if asks_horizon and not self._has_supported_horizon(context):
            return self._insufficient_response(
                symbol=symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="No sourced investment horizon is recorded for this query.",
            )
        if not self._has_verifiable_evidence(citations):
            return self._insufficient_response(
                symbol=symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="Available records are missing, stale, seeded/untraced, or lack a source citation.",
            )

        evidence_by_id = {item.id: item for item in citations}
        tool_context = {
            **context,
            "evidence_register": [item.model_dump(mode="json") for item in citations],
        }
        model = self.router.route_task(task_type, "HIGH" if task_type == "DEEP_RESEARCH" else "MEDIUM")
        draft_data, usage = await self.provider.generate_structured(
            prompt=build_chat_prompt(question, tool_context),
            system=SYSTEM_PROMPT,
            model=model,
            schema=AIAnswerDraft.model_json_schema(),
        )
        try:
            draft = AIAnswerDraft.model_validate(draft_data)
        except ValidationError as error:
            raise AIProviderError("AI provider response did not match the structured analyst schema.") from error

        cited_claims = []
        referenced_ids: set[str] = set()
        for claim in draft.claims:
            valid_ids = [citation_id for citation_id in claim.citation_ids if citation_id in evidence_by_id]
            if claim.claim_type != "UNCERTAINTY" and not valid_ids:
                return self._insufficient_response(
                    symbol=symbol,
                    as_of=requested_date,
                    citations=citations,
                    tools_used=used_tools,
                    reason="The model returned a factual or interpreted claim without a valid evidence citation.",
                )
            if claim.claim_type != "UNCERTAINTY" and any(
                evidence_by_id[citation_id].claim_type not in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"}
                or not evidence_by_id[citation_id].source
                or evidence_by_id[citation_id].data_origin in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED"}
                or evidence_by_id[citation_id].freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"}
                for citation_id in valid_ids
            ):
                return self._insufficient_response(
                    symbol=symbol,
                    as_of=requested_date,
                    citations=citations,
                    tools_used=used_tools,
                    reason="The selected citation is stale, untraced, or not a verifiable evidence source.",
                )
            if len(valid_ids) != len(claim.citation_ids):
                return self._insufficient_response(
                    symbol=symbol,
                    as_of=requested_date,
                    citations=citations,
                    tools_used=used_tools,
                    reason="The model referenced an evidence ID that was not supplied by a data tool.",
                )
            if claim.claim_type != "UNCERTAINTY":
                cited_numbers = set().union(*(
                    _numeric_values(json.dumps(evidence_by_id[citation_id].value, default=str))
                    for citation_id in valid_ids
                ))
                claim_numbers = _numeric_values(claim.text)
                if not claim_numbers.issubset(cited_numbers):
                    return self._insufficient_response(
                        symbol=symbol,
                        as_of=requested_date,
                        citations=citations,
                        tools_used=used_tools,
                        reason="A numeric claim is not present in the values of its cited evidence IDs.",
                    )
            referenced_ids.update(valid_ids)
            cited_claims.append(claim)

        if not cited_claims:
            return self._insufficient_response(
                symbol=symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="The model did not return any structured claims that can be safely displayed.",
            )

        uncertain_numbers = _numeric_values(" ".join(draft.uncertainty))
        if uncertain_numbers:
            return self._insufficient_response(
                symbol=symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="A numeric statement in the uncertainty field was suppressed because it has no citation IDs.",
            )

        uncertain = any(item.freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"} for item in citations)
        grounded_answer = " ".join(
            f"{claim.text} [Evidence: {', '.join(claim.citation_ids)}]" if claim.citation_ids else claim.text
            for claim in cited_claims
        )
        return AIChatResponse(
            status="PARTIAL" if uncertain else "AVAILABLE",
            symbol=symbol,
            as_of_date=requested_date,
            prompt_version=PROMPT_VERSION,
            model=usage.get("model", model),
            answer=grounded_answer,
            claims=cited_claims,
            citations=[item for item in citations if item.id in referenced_ids],
            uncertainty=draft.uncertainty,
            tools_used=used_tools,
            usage=usage,
        ).model_dump(mode="json")

    async def generate_daily_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Summarize only sourced market, regime, macro, event, and portfolio evidence for today.",
            session=session,
            as_of=as_of,
            tool_names=["macro", "regime", "events", "portfolio", "evidence"],
            task_type="DAILY_BRIEF",
        )

    async def generate_weekly_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Summarize evidence-backed changes in market, macro, events, opportunity, watchlist, and portfolio. State missing comparisons.",
            session=session,
            as_of=as_of,
            tool_names=["macro", "regime", "events", "opportunity", "portfolio", "watchlist", "historical_snapshot", "evidence"],
            task_type="WEEKLY_BRIEF",
        )

    async def generate_monthly_brief(self, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            "Review sourced portfolio, DCA, allocation, valuation, thesis, event, and data-quality evidence. Do not predict prices.",
            session=session,
            as_of=as_of,
            tool_names=["fundamentals", "valuation", "factors", "risk", "macro", "regime", "events", "opportunity", "portfolio", "watchlist", "historical_snapshot", "evidence"],
            task_type="MONTHLY_BRIEF",
        )

    async def analyze_stock(self, symbol: str, session: Session, as_of: date | None = None) -> dict[str, Any]:
        return await self.answer_question(
            f"Analyze {symbol} only from the selected evidence tools. Explain missing or stale inputs and avoid trade instructions.",
            session=session,
            symbol=symbol,
            as_of=as_of,
            task_type="STOCK_RESEARCH",
        )