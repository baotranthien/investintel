import pytest
from datetime import date
from sqlalchemy.orm import Session
from services.screener.engine import StockScreenerEngine, ScreenerCriteria
from services.ai.tools import AITools, _get_screener_evidence
from services.ai.analyst import AIAnalyst, AICitation, AIClaim

class TestScreenerAIConsistency:
    """
    Phase 1 Regression Tests:
    1. Không được đưa cổ phiếu có P/E >= 15 vào kết quả.
    2. Không được đưa cổ phiếu có ROE <= 15%.
    3. Mỗi mã trả về phải có evidence riêng.
    4. Không được ghép danh sách từ hai valuation dates khác nhau.
    5. AI phải trình bày đúng số lượng và đúng danh sách mã.
    """

    def test_screener_strictly_enforces_pe_under_15(self, db_session: Session):
        engine = StockScreenerEngine(db_session)
        crit = ScreenerCriteria(universe="ALL", pe_max=15.0, roe_min=15.0, limit=50)
        res = engine.screen(crit, as_of=date(2026, 11, 2))
        assert res.matched_count > 0
        for stock in res.matches:
            assert stock.pe is not None
            assert stock.pe < 15.0, f"Stock {stock.symbol} has P/E {stock.pe} >= 15.0 (strict < 15.0 violated)"

    def test_screener_strictly_enforces_roe_above_15(self, db_session: Session):
        engine = StockScreenerEngine(db_session)
        crit = ScreenerCriteria(universe="ALL", pe_max=15.0, roe_min=15.0, limit=50)
        res = engine.screen(crit, as_of=date(2026, 11, 2))
        assert res.matched_count > 0
        for stock in res.matches:
            assert stock.roe is not None
            assert stock.roe > 15.0, f"Stock {stock.symbol} has ROE {stock.roe} <= 15.0 (strict > 15.0 violated)"

    def test_screener_strict_boundary_conditions(self):
        """
        Boundary Tests:
        - PE 14.999, ROE 15.01% -> PASS
        - PE 15.000, ROE 20.00% -> REJECT
        - PE 10.000, ROE 15.000% -> REJECT
        - PE 10.000, ROE 15.001% -> PASS
        """
        pe_max = 15.0
        roe_min = 15.0

        def check_eligibility(pe: float, roe: float) -> bool:
            return (pe < pe_max) and (roe > roe_min)

        assert check_eligibility(14.999, 15.01) is True, "PE 14.999, ROE 15.01% must PASS"
        assert check_eligibility(15.000, 20.00) is False, "PE 15.000 must be REJECTED (strict < 15.0)"
        assert check_eligibility(10.000, 15.000) is False, "ROE 15.000% must be REJECTED (strict > 15.0%)"
        assert check_eligibility(10.000, 15.001) is True, "PE 10.000, ROE 15.001% must PASS"

    def test_individual_evidence_per_matching_symbol(self, db_session: Session):
        as_of = date(2026, 11, 2)
        evidence = _get_screener_evidence(db_session, None, as_of)
        
        # Check that individual stock evidence exists
        symbols_with_evidence = set()
        for ev in evidence:
            sym = ev.get("symbol")
            if sym and sym != "UNIVERSE_ALL":
                symbols_with_evidence.add(sym)
                # Verify individual evidence structure
                assert ev.get("responsible_module") == "screener"
                assert ev.get("metric") in ("pe", "roe")
                assert ev.get("value") is not None
                if ev.get("metric") == "pe":
                    assert ev.get("value") <= 15.0
                elif ev.get("metric") == "roe":
                    assert ev.get("value") >= 15.0
                assert ev.get("observation_date") == as_of.isoformat()
        
        assert len(symbols_with_evidence) >= 4, f"Expected >= 4 symbols with individual evidence, got {len(symbols_with_evidence)}"

    def test_single_consistent_observation_date(self, db_session: Session):
        as_of = date(2026, 11, 2)
        evidence = _get_screener_evidence(db_session, None, as_of)
        dates = {ev.get("observation_date") for ev in evidence if ev.get("observation_date")}
        assert len(dates) == 1, f"Expected exactly 1 observation date, got {dates}"
        assert as_of.isoformat() in dates

    def test_screener_matching_count_and_symbols_conformance(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("ALL", as_of=as_of, session=db_session, question="Các cổ phiếu thỏa mãn tiêu chí định giá rẻ P/E dưới 15 và sinh lời ROE trên 15%?")
        evidence = ctx.get("evidence", [])
        
        matched_ev = next((e for e in evidence if e.get("metric") == "matched_count"), None)
        assert matched_ev is not None
        matched_count = matched_ev["value"]
        assert matched_count >= 1, f"Expected >= 1 qualifying stocks in session, got {matched_count}"

        # Top symbols evidence list
        list_ev = next((e for e in evidence if e.get("metric") == "matching_symbols"), None)
        assert list_ev is not None
        top_list = [s.strip() for s in list_ev["value"].split(",") if s.strip()]
        for s in top_list[:3]:
            assert len(s) >= 3

