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


def _extract_token_interpretations(token_match: str) -> set[Decimal]:
    cleaned = token_match.rstrip("%")
    interpretations = set()
    # 1. As standard integer/float without commas (e.g. 84,873 -> 84873, 12.5 -> 12.5)
    try:
        interpretations.add(Decimal(cleaned.replace(",", "")).normalize())
    except (InvalidOperation, ValueError):
        pass
    # 2. As Vietnamese decimal comma (e.g. 24,813 -> 24.813, 1,45 -> 1.45)
    if cleaned.count(",") == 1:
        try:
            interpretations.add(Decimal(cleaned.replace(",", ".")).normalize())
        except (InvalidOperation, ValueError):
            pass
    return interpretations


def _extract_claim_number_tokens(text: str) -> list[set[Decimal]]:
    # Normalize duplicate dots in decimal expressions (e.g. 84.832.6% -> 84.8326%)
    cleaned_value = re.sub(r"(\d+\.\d+)\.(\d+)", r"\1\2", str(text))
    tokens = []
    for match in _NUMBER.findall(cleaned_value):
        interps = _extract_token_interpretations(match)
        if interps:
            tokens.append(interps)
    return tokens


def _numeric_values(value: str) -> set[Decimal]:
    found = set()
    cleaned_value = re.sub(r"(\d+\.\d+)\.(\d+)", r"\1\2", str(value))
    for match in _NUMBER.findall(cleaned_value):
        found.update(_extract_token_interpretations(match))
    return found


def _extract_evidence_numbers(ev: Any) -> set[Decimal]:
    metric_clean = str(ev.metric or "").replace("_", " ")
    raw_str = (
        f"{json.dumps(ev.value, default=str)} "
        f"{ev.observation_date or ''} "
        f"{ev.publication_date or ''} "
        f"{metric_clean} "
        f"{ev.note or ''}"
    )
    nums = _numeric_values(raw_str)
    val = ev.value
    if isinstance(val, (int, float, Decimal)):
        try:
            f_val = float(val)
            for r in (0, 1, 2, 3):
                nums.add(Decimal(str(round(f_val, r))).normalize())
            nums.add(Decimal(int(f_val)))
        except (ValueError, OverflowError, InvalidOperation):
            pass
    return nums


def _is_number_grounded(num: Decimal, cited_numbers: set[Decimal]) -> bool:
    if num in cited_numbers:
        return True
    num_f = float(num)
    for c in cited_numbers:
        c_f = float(c)
        # Check absolute tolerance for small values
        if abs(num_f - c_f) <= 0.05:
            return True
        # Check relative tolerance (0.5%) for larger numbers
        if abs(c_f) > 1e-6 and abs(num_f - c_f) / abs(c_f) <= 0.005:
            return True
    return False


class AIAnalyst:
    def __init__(self, provider: AIProvider | None = None, router: AIRouter | None = None):
        self.provider = provider or AIGateway()
        self.router = router or AIRouter()

    def _citations(self, context: dict[str, Any]) -> list[AICitation]:
        citations = []
        raw_evidence = context.get("evidence", [])
        if isinstance(raw_evidence, dict):
            evidence_items = []
            for module_name, items in raw_evidence.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item_copy = dict(item)
                            item_copy.setdefault("responsible_module", module_name)
                            evidence_items.append(item_copy)
                elif isinstance(items, dict):
                    item_copy = dict(items)
                    item_copy.setdefault("responsible_module", module_name)
                    evidence_items.append(item_copy)
        elif isinstance(raw_evidence, list):
            evidence_items = raw_evidence
        else:
            evidence_items = []

        for index, item in enumerate(evidence_items, start=1):
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
                is_estimate=item.get("is_estimate", False),
                diagnostic_reason=item.get("diagnostic_reason"),
                note=item.get("note"),
                symbol=item.get("symbol"),
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

    @staticmethod
    def _is_conversational_or_help(text: str) -> bool:
        cleaned = text.strip().lower()
        greetings = {
            "chào", "chao", "xin chào", "xin chao", "hi", "hello", "hey",
            "chào bạn", "chao ban", "chào bot", "chao bot", "alo", "alo bot",
            "hello bot", "hi bot",
        }
        if cleaned in greetings:
            return True
        help_patterns = [
            r"^(?:xin\s+)?chào(?:\s+bạn|\s+bot)?[\s!.,?]*$",
            r"^(?:hi|hello|hey)(?:\s+bot)?[\s!.,?]*$",
            r"^(?:bạn|bot)\s+(?:là\s+ai|tên\s+gì)[\s?]*$",
            r"^(?:who\s+are\s+you|what\s+can\s+you\s+do)[\s?]*$",
            r"^(?:hướng\s+dẫn|huong\s+dan|help|trợ\s+giúp|tro\s+giup)[\s?]*$",
            r"^(?:bạn|bot)\s+(?:có\s+thể\s+làm\s+gì|giúp\s+gì|làm\s+được\s+gì)[\s?]*$",
            r"^(?:tính\s+năng|chức\s+năng|gioi\s+thieu|giới\s+thiệu)[\s?]*$",
        ]
        return any(re.search(pat, cleaned, re.IGNORECASE) for pat in help_patterns)

    def _conversational_response(self, as_of: date) -> dict[str, Any]:
        return AIChatResponse(
            status="AVAILABLE",
            symbol=None,
            resolved_symbol=None,
            as_of_date=as_of,
            prompt_version=PROMPT_VERSION,
            model="investintel-assistant",
            answer=(
                "Xin chào! Tôi là Trợ lý Phân tích Định lượng & Nghiên cứu Doanh nghiệp của InvestIntel.\n\n"
                "Tôi có thể hỗ trợ bạn tra cứu và phân tích dữ liệu kiểm chứng cho toàn bộ danh mục cổ phiếu và chứng khoán được hỗ trợ:\n"
                "1. **Định giá & Sức khỏe tài chính:** Hỏi về doanh thu, biên lợi nhuận, P/E, P/B, nợ vay (ví dụ: *'giá VCB'*, *'định giá FPT'*, *'doanh thu MWG'*).\n"
                "2. **Toàn cảnh thị trường:** Hỏi về chỉ số và chế độ thị trường (ví dụ: *'thị trường hôm nay'*, *'tổng quan VN-Index'*).\n"
                "3. **Luận điểm & Rủi ro:** Kiểm tra tín hiệu cơ hội, điểm rủi ro tổng hợp (ví dụ: *'rủi ro HPG'*, *'đánh giá SHB'*).\n\n"
                "Mẹo: Bạn có thể nhập trực tiếp tên mã cổ phiếu vào câu hỏi hoặc điền mã vào ô 'Mã cổ phiếu' phía trên."
            ),
            claims=[
                AIClaim(
                    claim_type="FACT",
                    text="InvestIntel hỗ trợ phân tích toàn bộ các cổ phiếu và chứng khoán trong cơ sở dữ liệu với dữ liệu tài chính, định giá và rủi ro được kiểm chứng đa tầng.",
                    citation_ids=[],
                )
            ],
            citations=[],
            uncertainty=[],
            tools_used=[],
            usage={"eval_count": 50},
        ).model_dump(mode="json")

    def _insufficient_response(
        self,
        *,
        symbol: str | None,
        as_of: date,
        citations: list[AICitation],
        tools_used: list[str],
        reason: str,
        answer: str = "Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.",
    ) -> dict[str, Any]:
        return AIChatResponse(
            status="INSUFFICIENT_DATA",
            symbol=symbol,
            resolved_symbol=symbol,
            as_of_date=as_of,
            prompt_version=PROMPT_VERSION,
            model=None,
            answer=answer,
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
        from services.universe.registry import UniverseRegistry

        requested_date = as_of or date.today()

        # Handle conversational greetings and guidance if no specific symbol is supplied
        if self._is_conversational_or_help(question) and not symbol:
            return self._conversational_response(requested_date)

        extracted_symbols: list[str] = []
        canonical_symbol = None
        if symbol:
            resolved = UniverseRegistry.resolve_instrument(session, symbol)
            canonical_symbol = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(symbol) or symbol.upper())
            extracted_symbols = [canonical_symbol]
        else:
            extracted_symbols = UniverseRegistry.extract_all_symbols_from_text(question, session)
            canonical_symbol = extracted_symbols[0] if extracted_symbols else None

        # Check for general portfolio or asset allocation query without specific single ticker (Q19)
        portfolio_terms = (
            "danh mục", "danh muc", "phân bổ", "phan bo", "portfolio", "allocation",
            "tài sản", "tai san", "100 triệu", "đa dạng hóa", "da dang hoa", "chiến lược",
        )
        is_portfolio_query = any(term in question.casefold() for term in portfolio_terms)
        if not extracted_symbols and is_portfolio_query:
            extracted_symbols = ["VN100"]
            canonical_symbol = "VN100"

        query_target = extracted_symbols if len(extracted_symbols) > 1 else canonical_symbol
        context = AITools.get_context(query_target, requested_date, tool_names, session)
        citations = self._citations(context)
        used_tools = [item["name"] for item in context.get("tools", [])]
        asks_horizon = any(term in question.casefold() for term in (
            "horizon", "investment period", "time horizon", "thời hạn", "kỳ hạn", "đầu tư bao lâu",
        ))
        if asks_horizon and not self._has_supported_horizon(context):
            return self._insufficient_response(
                symbol=canonical_symbol or symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason="No sourced investment horizon is recorded for this query.",
            )
        if not self._has_verifiable_evidence(citations):
            effective_symbol = canonical_symbol or symbol
            if effective_symbol:
                detail_reason = f"Available records for {effective_symbol} are missing, stale, seeded/untraced, or lack a source citation (as of {requested_date})."
                ans_text = f"Chưa đủ bằng chứng có nguồn kiểm chứng về mã {effective_symbol} để trả lời câu hỏi này."
            else:
                detail_reason = "Không tìm thấy mã cổ phiếu hợp lệ trong câu hỏi hoặc mã chưa có trong cơ sở dữ liệu."
                ans_text = (
                    "Chưa xác định được mã cổ phiếu hoặc chủ đề cần phân tích. "
                    "Bạn vui lòng nhập rõ mã cổ phiếu (ví dụ: VCB, FPT, HPG) hoặc đặt câu hỏi về thị trường chung (ví dụ: 'thị trường hôm nay')."
                )
            return self._insufficient_response(
                symbol=effective_symbol,
                as_of=requested_date,
                citations=citations,
                tools_used=used_tools,
                reason=detail_reason,
                answer=ans_text,
            )

        # Check for intraday historical timestamp request (Q18)
        asks_intraday = bool(re.search(r"\b(?:1[0-9]|2[0-3]|0?[0-9]):[0-5][0-9]\b", question))

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
        suppressed_reasons: list[str] = []
        for claim in draft.claims:
            normalized_cids = []
            for raw_cid in claim.citation_ids:
                cid_str = str(raw_cid).strip().strip("[]").upper()
                m = re.match(r"^E(\d+)$", cid_str)
                if m:
                    cid_str = f"E{int(m.group(1)):03d}"
                normalized_cids.append(cid_str)
            claim.citation_ids = normalized_cids

            valid_ids = [citation_id for citation_id in claim.citation_ids if citation_id in evidence_by_id]
            if claim.claim_type != "UNCERTAINTY" and not valid_ids:
                suppressed_reasons.append("The model returned a factual or interpreted claim without a valid evidence citation.")
                continue
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
            if claim.claim_type == "UNCERTAINTY":
                valid_ids = []
                claim.citation_ids = []
            elif len(valid_ids) != len(claim.citation_ids):
                suppressed_reasons.append("The model referenced an evidence ID that was not supplied by a data tool.")
                continue
            if claim.claim_type != "UNCERTAINTY":
                claim_text_lower = claim.text.lower()

                # Entity consistency: if claim mentions stock A, citations must not belong solely to stock B
                has_entity_mismatch = False
                if extracted_symbols:
                    for sym in extracted_symbols:
                        if sym and sym != "VN100":
                            sym_re = rf"\b{re.escape(sym.lower())}\b"
                            if re.search(sym_re, claim_text_lower):
                                foreign = [cid for cid in valid_ids if evidence_by_id[cid].symbol and evidence_by_id[cid].symbol != sym and evidence_by_id[cid].symbol != "VN100"]
                                if foreign and not any(evidence_by_id[cid].symbol == sym for cid in valid_ids):
                                    suppressed_reasons.append(f"Claim for {sym} cannot be supported solely by citations from {evidence_by_id[foreign[0]].symbol}.")
                                    has_entity_mismatch = True
                                    break
                if has_entity_mismatch:
                    continue

                # Metric semantic validation:
                # 1. P/E vs P/B
                if any(term in claim_text_lower for term in ("p/b", "pb", "price-to-book", "price to book")):
                    if any(evidence_by_id[cid].metric in ("pe", "pe_ratio", "price_to_earnings") for cid in valid_ids):
                        suppressed_reasons.append("P/E evidence cannot be presented as P/B.")
                        continue
                if any(term in claim_text_lower for term in ("p/e", "pe", "price-to-earnings", "price to earnings")):
                    if any(evidence_by_id[cid].metric in ("pb", "pb_ratio", "price_to_book") for cid in valid_ids):
                        suppressed_reasons.append("P/B evidence cannot be presented as P/E.")
                        continue

                # 2. Gross margin vs Revenue growth / decline (Q06 VHM)
                is_revenue_claim = bool(
                    re.search(r"\bdoanh\s*thu\b.*?\b(?:tăng|giảm|tăng\s*trưởng|suy\s*giảm|growth|decline)\b", claim_text_lower)
                    or re.search(r"\b(?:tăng\s*trưởng|suy\s*giảm)\s+doanh\s*thu\b", claim_text_lower)
                    or any(term in claim_text_lower for term in ("revenue growth", "revenue decline"))
                )
                if is_revenue_claim:
                    if any(evidence_by_id[cid].metric in ("gross_margin", "net_margin", "ebitda_margin") for cid in valid_ids) and not any(evidence_by_id[cid].metric in ("revenue", "revenue_yoy", "revenue_cagr_3y", "revenue_cagr_5y") for cid in valid_ids):
                        suppressed_reasons.append("Margin evidence cannot be presented as revenue growth or decline.")
                        continue

                # 3. P/E multiple vs Profit / Net income (Q07 VIC)
                if any(term in claim_text_lower for term in ("lợi nhuận hợp nhất", "lợi nhuận thuần", "net profit", "lợi nhuận sau thuế")):
                    if any(evidence_by_id[cid].metric in ("pe", "pe_ratio", "pb", "pb_ratio") for cid in valid_ids) and not any(evidence_by_id[cid].metric in ("net_income", "net_income_yoy", "operating_income") for cid in valid_ids):
                        suppressed_reasons.append("Valuation multiple evidence cannot be presented as profit or income.")
                        continue

                # 4. Company revenue vs Commodity/Oil price (Q10 PLX)
                if any(term in claim_text_lower for term in ("giá dầu", "oil price", "giá hàng hóa")):
                    if any(evidence_by_id[cid].metric in ("revenue", "revenue_yoy", "gross_margin", "net_income") for cid in valid_ids):
                        suppressed_reasons.append("Company financial statements cannot substantiate commodity price changes without a market price series.")
                        continue

                # Numeric grounding check
                cited_numbers = set().union(*(
                    _extract_evidence_numbers(evidence_by_id[citation_id])
                    for citation_id in valid_ids
                    if citation_id in evidence_by_id
                )).union(_numeric_values(question))
                claim_tokens = _extract_claim_number_tokens(claim.text)
                is_grounded = all(
                    any(_is_number_grounded(interp, cited_numbers) for interp in token_interps)
                    for token_interps in claim_tokens
                )
                if not is_grounded:
                    suppressed_reasons.append("A numeric claim is not present in the values of its cited evidence IDs.")
                    continue

            referenced_ids.update(valid_ids)
            cited_claims.append(claim)

        # Ensure at least one substantive claim survived validation before adding notices
        valid_substantive_claims = [c for c in cited_claims if c.claim_type != "UNCERTAINTY"]
        if not valid_substantive_claims:
            if draft.answer and draft.answer.strip():
                clean_ans = draft.answer.strip()
                ans_numbers = _numeric_values(clean_ans)
                if not ans_numbers:
                    cited_claims.append(AIClaim(claim_type="UNCERTAINTY", text=clean_ans, citation_ids=[]))
                    valid_substantive_claims = [c for c in cited_claims if c.claim_type != "UNCERTAINTY"]
            if not valid_substantive_claims:
                reason = suppressed_reasons[0] if suppressed_reasons else "The model did not return any structured claims that can be safely displayed."
                return self._insufficient_response(
                    symbol=canonical_symbol or symbol,
                    as_of=requested_date,
                    citations=citations,
                    tools_used=used_tools,
                    reason=reason,
                )

        # If intraday timestamp requested, inject honesty notice regarding EOD limitation (Q18)
        if asks_intraday:
            cited_claims.insert(0, AIClaim(
                claim_type="UNCERTAINTY",
                text=f"Lưu ý: Hệ thống InvestIntel hiện chỉ hỗ trợ dữ liệu chốt phiên theo ngày (EOD), không hỗ trợ replay dữ liệu tại thời điểm trong phiên giao dịch. Kết quả dưới đây được tổng hợp dựa trên dữ liệu chốt phiên ngày {requested_date.isoformat()}.",
                citation_ids=[],
            ))

        # If multi-ticker comparison, verify if any requested stock has missing evidence
        if len(extracted_symbols) > 1:
            for req_sym in extracted_symbols:
                has_sym = any(
                    (evidence_by_id.get(cid) and evidence_by_id[cid].symbol == req_sym)
                    for c in cited_claims for cid in c.citation_ids
                )
                if not has_sym and not any(req_sym.lower() in c.text.lower() for c in cited_claims):
                    cited_claims.append(AIClaim(
                        claim_type="UNCERTAINTY",
                        text=f"Dữ liệu tài chính và định giá cho mã {req_sym} hiện chưa có sẵn hoặc chưa đủ điều kiện kiểm chứng trong hệ thống.",
                        citation_ids=[],
                    ))

        # Filter contradictory uncertainty statements (e.g. claiming P/E missing when P/E was evidenced in claims)
        available_metrics = {
            evidence_by_id[cid].metric.lower()
            for c in cited_claims
            for cid in c.citation_ids
            if cid in evidence_by_id and evidence_by_id[cid].metric
        }
        cleaned_uncertainty = []
        for unc in draft.uncertainty:
            unc_lower = unc.lower()
            contradicts = False
            if "p/e" in unc_lower and any(m in ("pe", "pe_ratio", "price_to_earnings") for m in available_metrics):
                contradicts = True
            elif "p/b" in unc_lower and any(m in ("pb", "pb_ratio", "price_to_book") for m in available_metrics):
                contradicts = True
            elif ("biên lợi nhuận" in unc_lower or "gross margin" in unc_lower) and "gross_margin" in available_metrics:
                contradicts = True
            if not contradicts:
                cleaned_uncertainty.append(unc)

        # Sanitize ungrounded numbers from uncertainty statements instead of discarding entire response
        allowed_uncertainty_numbers = set().union(*(
            _numeric_values(f"{c.metric or ''} {c.observation_date or ''}")
            for c in citations
        )).union(_numeric_values(question))

        final_uncertainty = []
        for unc in cleaned_uncertainty:
            unc_numbers = _numeric_values(unc)
            if not (unc_numbers - allowed_uncertainty_numbers):
                final_uncertainty.append(unc)
            else:
                stripped = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", "", unc).strip()
                if stripped and len(stripped) > 5:
                    final_uncertainty.append(stripped)

        has_uncertainty = (
            asks_intraday
            or any(c.claim_type == "UNCERTAINTY" for c in cited_claims)
            or any(item.freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"} for item in citations if item.id in referenced_ids)
            or (len(extracted_symbols) > 1 and any(
                not any(evidence_by_id.get(cid) and evidence_by_id[cid].symbol == s for c in cited_claims for cid in c.citation_ids)
                for s in extracted_symbols
            ))
        )
        grounded_answer = " ".join(
            f"{claim.text} [Evidence: {', '.join(claim.citation_ids)}]" if claim.citation_ids else claim.text
            for claim in cited_claims
        )
        returned_citations = [item for item in citations if item.id in referenced_ids]
        if not returned_citations and any(self._has_verifiable_evidence([c]) for c in citations):
            returned_citations = [c for c in citations if self._has_verifiable_evidence([c])][:15]

        return AIChatResponse(
            status="PARTIAL" if has_uncertainty else "AVAILABLE",
            symbol=", ".join(extracted_symbols) if len(extracted_symbols) > 1 else (canonical_symbol or symbol),
            resolved_symbol=canonical_symbol or symbol,
            as_of_date=requested_date,
            prompt_version=PROMPT_VERSION,
            model=usage.get("model", model),
            answer=grounded_answer,
            claims=cited_claims,
            citations=returned_citations,
            uncertainty=final_uncertainty,
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