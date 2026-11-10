import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Asset
from services.market.trading_hours import get_effective_trading_date
from services.research.backtest import BacktestConfig, BacktestResult, HistoricalBacktestEngine
from services.research.workspace import ResearchWorkspace, build_research_workspace
from services.research.analysis import DeepCompanyAnalysis, CompanyDeepAnalysisEngine
from services.research.history import HistoricalFinancialDataset, HistoricalFinancialEngine
from services.research.report import InstitutionalInvestmentReport, InvestmentReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _verify_asset_exists(session: Session, symbol: str) -> None:
    asset = session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol.upper()} is not registered.")


@router.get("/{symbol}/report", response_model=InstitutionalInvestmentReport)
def get_investment_report(
    symbol: str,
    as_of: date = Query(default_factory=get_effective_trading_date, description="Point-in-time date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> InstitutionalInvestmentReport:
    """Return a comprehensive 13-section institutional investment research report."""
    _verify_asset_exists(session, symbol)
    engine = InvestmentReportGenerator(session)
    try:
        return engine.generate_report(symbol, as_of)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Report unavailable for {symbol.upper()}: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error generating report for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=f"Internal error generating report for {symbol.upper()}.")


@router.get("/{symbol}/analysis", response_model=DeepCompanyAnalysis)
def get_deep_company_analysis(
    symbol: str,
    as_of: date = Query(default_factory=get_effective_trading_date, description="Point-in-time date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> DeepCompanyAnalysis:
    """Return an institutional 7-section deep company investment analysis."""
    _verify_asset_exists(session, symbol)
    engine = CompanyDeepAnalysisEngine(session)
    try:
        return engine.generate_analysis(symbol, as_of)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Analysis unavailable for {symbol.upper()}: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error generating analysis for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=f"Internal error generating analysis for {symbol.upper()}.")


@router.get("/{symbol}/history", response_model=HistoricalFinancialDataset)
def get_historical_financial_dataset(
    symbol: str,
    as_of: date = Query(default_factory=get_effective_trading_date, description="Point-in-time date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> HistoricalFinancialDataset:
    """Return 5-year annual and 12-quarter longitudinal financial time-series with corporate actions."""
    _verify_asset_exists(session, symbol)
    engine = HistoricalFinancialEngine(session)
    try:
        return engine.get_historical_dataset(symbol, as_of)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Historical dataset unavailable for {symbol.upper()}: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error retrieving historical dataset for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail=f"Internal error retrieving historical dataset for {symbol.upper()}.")


@router.post("/backtest", response_model=BacktestResult)
def run_backtest(
    config: BacktestConfig,
    session: Session = Depends(get_db),
) -> BacktestResult:
    """Execute point-in-time historical backtest and replay simulation."""
    engine = HistoricalBacktestEngine(session)
    return engine.run_backtest(config)


@router.get("/{symbol}", response_model=ResearchWorkspace)
def get_research_workspace(
    symbol: str,
    as_of: date = Query(default_factory=get_effective_trading_date, description="Point-in-time date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> ResearchWorkspace:
    """Return a canonical, evidence-first asset research workspace."""
    result = build_research_workspace(session, symbol, as_of)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Asset {symbol.upper()} is not registered.")
    return result
