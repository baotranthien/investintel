"""
Fundamental API Router — Phase 2 (Canonical Database Connected).

End-to-End Pipeline:
  Database (PostgreSQL)
  -> FinancialRepository
  -> Canonical Point-In-Time Records
  -> FundamentalSnapshotBuilder
  -> FundamentalSnapshot

Endpoints:
  GET /api/v1/fundamentals/{symbol}              — overview (with metrics, sector_metrics, quality, provenance)
  GET /api/v1/fundamentals/{symbol}/snapshot     — full snapshot (AI-ready)
  GET /api/v1/fundamentals/{symbol}/income-statement
  GET /api/v1/fundamentals/{symbol}/balance-sheet
  GET /api/v1/fundamentals/{symbol}/cash-flow
  GET /api/v1/fundamentals/{symbol}/ratios
  GET /api/v1/fundamentals/{symbol}/growth
  GET /api/v1/fundamentals/{symbol}/quality
  GET /api/v1/fundamentals/{symbol}/segments
  GET /api/v1/fundamentals/formula-registry
  GET /api/v1/fundamentals/sector-map
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from datetime import date as date_cls

from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.fundamentals.formula_registry import FORMULA_REGISTRY, list_formulas
from services.fundamentals.sector_models import COMPANY_SECTOR_MAP
from services.fundamentals.fixtures import FIXTURES

router = APIRouter(prefix="/api/v1/fundamentals", tags=["fundamentals"])


def _load_company_dataset(symbol: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads company fundamental dataset from Canonical Database via FinancialRepository.
    Enforces strict PIT filtering: publication_date <= as_of.
    Falls back to FIXTURES only for synthetic test symbols (starting with FIXTURE_).
    """
    sym = symbol.upper()
    as_of_date = None
    if as_of:
        try:
            as_of_date = date_cls.fromisoformat(as_of)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid as_of date format. Use YYYY-MM-DD.")

    # 1. Primary: Canonical Database
    with FinancialRepository() as repo:
        dataset = repo.get_financial_dataset(sym, as_of_date=as_of_date)
        if dataset and (dataset["income_annual"] or dataset["income_quarters"]):
            return dataset

    # 2. Test Fixture Fallback (strictly labeled as SYNTHETIC_FIXTURE)
    if sym.startswith("FIXTURE_") or sym in FIXTURES:
        fixture_data = FIXTURES.get(sym) or FIXTURES.get(sym.replace("FIXTURE_", ""))
        if fixture_data:
            return {
                "symbol": sym,
                "profile": {
                    "symbol": sym,
                    "name": f"Synthetic Fixture {sym}",
                    "exchange": "HOSE",
                    "sector": fixture_data.get("sector", "GENERAL"),
                },
                "sector": fixture_data.get("sector", "GENERAL"),
                "income_annual": fixture_data.get("income_annual", []),
                "income_quarters": fixture_data.get("income_quarters", []),
                "balance_annual": fixture_data.get("balance_annual", []),
                "cashflow_annual": fixture_data.get("cashflow_annual", []),
                "shares_outstanding": fixture_data.get("shares_outstanding"),
                "sources": ["SYNTHETIC_FIXTURE"],
                "as_of": as_of_date.isoformat() if as_of_date else None,
                "provenance": {
                    "source": "SYNTHETIC_FIXTURE",
                    "note": "Non-production fixture for unit test coverage only"
                }
            }

    raise HTTPException(
        status_code=404,
        detail=f"Company '{sym}' not found in canonical database. Available ingested symbols: FPT, VCB, MBB, MWG, HPG."
    )


def _build_snapshot_from_dataset(dataset: Dict[str, Any], as_of_date: Optional[date_cls] = None) -> Dict[str, Any]:
    """Helper to build FundamentalSnapshot from loaded dataset."""
    builder = FundamentalSnapshotBuilder(dataset["symbol"], dataset["sector"])
    return builder.build_snapshot(
        income_quarters=dataset["income_quarters"],
        income_annual=dataset["income_annual"],
        balance_annual=dataset["balance_annual"],
        cashflow_annual=dataset["cashflow_annual"],
        as_of_date=as_of_date,
        shares_outstanding=dataset.get("shares_outstanding"),
        sources=dataset.get("sources", ["CANONICAL_DATABASE"]),
    )


@router.get("/{symbol}", summary="Tổng quan cơ bản — Company fundamental overview")
def get_fundamental_overview(symbol: str, as_of: Optional[str] = Query(None, description="As-of date (YYYY-MM-DD)")):
    """
    Returns company overview with metrics, sector_metrics, quality, and provenance.
    Reads strictly from Canonical Database.
    """
    dataset = _load_company_dataset(symbol, as_of=as_of)
    as_of_date = date_cls.fromisoformat(as_of) if as_of else None
    snapshot = _build_snapshot_from_dataset(dataset, as_of_date=as_of_date)

    prof = dataset["profile"]
    return {
        "symbol": dataset["symbol"],
        "name": prof.get("name", dataset["symbol"]),
        "exchange": prof.get("exchange", "HOSE"),
        "sector": dataset["sector"],
        "as_of": snapshot.get("as_of"),
        "source": dataset.get("sources", ["CANONICAL_DATABASE"])[0],
        "sources": dataset.get("sources", ["CANONICAL_DATABASE"]),
        "data_status": "VALID",
        "metrics": {
            **snapshot.get("profitability", {}),
            **snapshot.get("growth", {}),
            **snapshot.get("per_share", {}),
            **snapshot.get("efficiency", {}),
        },
        "sector_metrics": snapshot.get("sector_metrics", {}),
        "quality": {
            "earnings_quality": snapshot.get("earnings_quality", {}),
            "financial_health": snapshot.get("financial_health", {}),
            "flags": snapshot.get("flags", []),
        },
        "provenance": dataset.get("provenance", {}),
        "years_of_history": len(dataset["income_annual"]),
        "latest_fiscal_year": dataset["income_annual"][-1].get("fiscal_year") if dataset["income_annual"] else None,
        "data_available": {
            "income_statement": len(dataset["income_annual"]) > 0,
            "balance_sheet": len(dataset["balance_annual"]) > 0,
            "cash_flow": len(dataset["cashflow_annual"]) > 0,
            "quarterly_data": len(dataset["income_quarters"]) > 0,
        },
    }


@router.get("/{symbol}/snapshot", summary="Snapshot toàn diện — Full fundamental snapshot")
def get_fundamental_snapshot(
    symbol: str,
    as_of: Optional[str] = Query(None, description="ISO date for historical reconstruction (YYYY-MM-DD)"),
):
    """
    Returns full fundamental snapshot — AI-ready JSON.
    Supports as_of parameter for point-in-time historical reconstruction.
    """
    dataset = _load_company_dataset(symbol, as_of=as_of)
    as_of_date = date_cls.fromisoformat(as_of) if as_of else None
    snapshot = _build_snapshot_from_dataset(dataset, as_of_date=as_of_date)
    snapshot["provenance"] = dataset.get("provenance", {})
    return snapshot


@router.get("/{symbol}/income-statement", summary="Báo cáo KQKD — Income Statement")
def get_income_statement(symbol: str, period: str = Query("ANNUAL", description="ANNUAL | QUARTERLY")):
    """Returns canonical normalized income statement data from DB."""
    dataset = _load_company_dataset(symbol)
    data = dataset["income_annual"] if period.upper() == "ANNUAL" else dataset["income_quarters"]
    return {
        "symbol": dataset["symbol"],
        "statement_type": "INCOME_STATEMENT",
        "period_type": period.upper(),
        "currency": "VND",
        "unit_scale": "BILLION_VND",
        "data": data,
        "data_quality": {
            "completeness": 1.0 if data else 0.0,
            "source": dataset.get("sources", ["CANONICAL_DATABASE"])[0],
        },
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/balance-sheet", summary="Bảng cân đối kế toán — Balance Sheet")
def get_balance_sheet(symbol: str):
    """Returns canonical normalized balance sheet data from DB."""
    dataset = _load_company_dataset(symbol)
    return {
        "symbol": dataset["symbol"],
        "statement_type": "BALANCE_SHEET",
        "currency": "VND",
        "unit_scale": "BILLION_VND",
        "data": dataset["balance_annual"],
        "data_quality": {
            "completeness": 1.0 if dataset["balance_annual"] else 0.0,
            "source": dataset.get("sources", ["CANONICAL_DATABASE"])[0],
        },
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/cash-flow", summary="Báo cáo lưu chuyển tiền tệ — Cash Flow Statement")
def get_cash_flow(symbol: str):
    """Returns canonical normalized cash flow statement data from DB."""
    dataset = _load_company_dataset(symbol)
    return {
        "symbol": dataset["symbol"],
        "statement_type": "CASH_FLOW",
        "currency": "VND",
        "unit_scale": "BILLION_VND",
        "data": dataset["cashflow_annual"],
        "data_quality": {
            "completeness": 1.0 if dataset["cashflow_annual"] else 0.0,
            "source": dataset.get("sources", ["CANONICAL_DATABASE"])[0],
        },
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/ratios", summary="Tỷ số tài chính — Financial Ratios")
def get_ratios(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns key financial ratios from canonical DB snapshot."""
    dataset = _load_company_dataset(symbol, as_of=as_of)
    as_of_date = date_cls.fromisoformat(as_of) if as_of else None
    snap = _build_snapshot_from_dataset(dataset, as_of_date=as_of_date)
    return {
        "symbol": dataset["symbol"],
        "period": snap["period"],
        "as_of": snap["as_of"],
        "ratios": {
            **snap["profitability"],
            **snap["balance_sheet"],
            **snap["cash_flow"],
            **snap["efficiency"],
        },
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/growth", summary="Tăng trưởng — Growth Metrics")
def get_growth(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns growth metrics: YoY, CAGR, trend, acceleration from DB."""
    dataset = _load_company_dataset(symbol, as_of=as_of)
    as_of_date = date_cls.fromisoformat(as_of) if as_of else None
    snap = _build_snapshot_from_dataset(dataset, as_of_date=as_of_date)
    return {
        "symbol": dataset["symbol"],
        "period": snap["period"],
        "as_of": snap["as_of"],
        "growth": snap["growth"],
        "trends": snap["trends"],
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/quality", summary="Chất lượng lợi nhuận — Earnings Quality")
def get_earnings_quality(symbol: str, as_of: Optional[str] = Query(None)):
    """Returns earnings quality analysis, one-off detection and quality flags from DB."""
    dataset = _load_company_dataset(symbol, as_of=as_of)
    as_of_date = date_cls.fromisoformat(as_of) if as_of else None
    snap = _build_snapshot_from_dataset(dataset, as_of_date=as_of_date)
    return {
        "symbol": dataset["symbol"],
        "as_of": snap["as_of"],
        "earnings_quality": snap["earnings_quality"],
        "cash_flow": snap["cash_flow"],
        "flags": snap["flags"],
        "financial_health": snap["financial_health"],
        "provenance": dataset.get("provenance", {})
    }


@router.get("/{symbol}/segments", summary="Phân khúc — Segment Data")
def get_segments(symbol: str):
    """Segment breakdown — returns honest status if not disclosed."""
    dataset = _load_company_dataset(symbol)
    return {
        "symbol": dataset["symbol"],
        "status": "NOT_AVAILABLE",
        "message": "Segment data requires official notes disclosure. Not currently available in canonical pipeline.",
        "data": [],
        "provenance": dataset.get("provenance", {})
    }


@router.get("/formula-registry", summary="Danh mục công thức — Formula Registry")
def get_formula_registry(scope: Optional[str] = None, sector: Optional[str] = None):
    """Returns the formula registry for all financial metrics."""
    specs = list_formulas(scope=scope, sector=sector)
    return {
        "count": len(specs),
        "formulas": [
            {
                "metric_id": s.metric_id,
                "name": s.name,
                "name_vi": s.name_vi,
                "formula": s.formula,
                "version": s.version,
                "unit": s.unit,
                "scope": s.scope,
                "sector": s.sector,
                "description": s.description,
                "caveats": s.caveats,
            }
            for s in specs
        ],
    }


@router.get("/sector-map", summary="Bảng phân ngành — Sector Map")
def get_sector_map():
    """Returns the company-to-sector mapping."""
    return {
        "count": len(COMPANY_SECTOR_MAP),
        "sector_map": COMPANY_SECTOR_MAP,
    }
