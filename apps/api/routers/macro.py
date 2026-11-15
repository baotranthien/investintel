from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.connection import get_db
from services.macro.engine import MacroEngine, MarketRegimeEngine
from services.macro.observations import MacroLatestResponse, get_latest_macro_series
from services.market.trading_hours import get_effective_trading_date, get_vn_now

router = APIRouter(prefix="/api/v1/macro", tags=["macro", "regime"])

@router.get("/dashboard")
def get_macro_dashboard():
    """Returns the consolidated Macro Dashboard with regime states and variables."""
    return MacroEngine.get_dashboard(get_effective_trading_date())

@router.get("/market-regime")
def get_market_regime():
    """Returns the current market regime (e.g. EXPANSION, RISK_OFF)."""
    return MarketRegimeEngine.determine_regime(get_effective_trading_date())


@router.get("/observations/latest", response_model=MacroLatestResponse)
def get_latest_macro_observations(session: Session = Depends(get_db)) -> MacroLatestResponse:
    """Return the latest published canonical observation for each registered macro series."""
    cutoff = max(get_effective_trading_date(), get_vn_now().date())
    return get_latest_macro_series(session, cutoff)


@router.get("/news-analysis")
def get_macro_news_analysis(
    approved_only: bool = True,
    limit: int = 24,
    session: Session = Depends(get_db),
):
    """Return latest validated 17:30 ICT official news macro-stock correlation JSON from Supabase."""
    from database.models import MacroAnalysisLog

    q = session.query(MacroAnalysisLog)
    total_count = session.query(MacroAnalysisLog).count()
    approved_count = session.query(MacroAnalysisLog).filter(MacroAnalysisLog.approved_for_ai.is_(True)).count()
    needs_review_count = max(0, total_count - approved_count)
    if approved_only:
        q = q.filter(MacroAnalysisLog.approved_for_ai.is_(True))
    rows = (
        q.order_by(MacroAnalysisLog.analysis_date.desc(), MacroAnalysisLog.source_trust_level.desc(), MacroAnalysisLog.id.desc())
        .limit(limit)
        .all()
    )
    events = [
        {
            "id": r.id,
            "date": r.analysis_date.isoformat() if r.analysis_date else None,
            "title": r.event_title,
            "url": r.source_url,
            "source_domain": r.source_domain,
            "source_tier": r.source_tier,
            "source_trust_level": r.source_trust_level,
            "macro_impact": r.macro_impact,
            "stock_market_correlation": {
                "type": r.correlation_type,
                "sentiment": r.sentiment,
                "affected_sectors": r.affected_sectors or [],
                "affected_symbols": r.affected_symbols or [],
                "analysis": r.analysis_detail,
            },
            "ai_confidence_score": float(r.ai_confidence_score) if r.ai_confidence_score is not None else 0.0,
            "validation": {
                "status": r.validation_status,
                "approved_for_ai": r.approved_for_ai,
                "historical_hit_rate": float(r.historical_hit_rate) if r.historical_hit_rate is not None else None,
                "sample_size": r.historical_sample_size or 0,
                "avg_1d_return_pct": float(r.avg_1d_return_pct) if r.avg_1d_return_pct is not None else None,
                "avg_5d_return_pct": float(r.avg_5d_return_pct) if r.avg_5d_return_pct is not None else None,
                "notes": r.validation_notes,
            },
            "raw_gemini_json": r.raw_event_json
            if isinstance(r.raw_event_json, dict)
            else {
                "title": r.event_title,
                "url": r.source_url,
                "macro_impact": r.macro_impact,
                "stock_market_correlation": {
                    "type": r.correlation_type,
                    "sentiment": r.sentiment,
                    "affected_sectors": r.affected_sectors or [],
                    "affected_symbols": r.affected_symbols or [],
                    "analysis": r.analysis_detail,
                },
                "ai_confidence_score": float(r.ai_confidence_score) if r.ai_confidence_score is not None else 0.0,
            },
        }
        for r in rows
    ]
    latest_date = events[0]["date"] if events else get_vn_now().date().isoformat()
    return {
        "date": latest_date,
        "schedule_ict": "17:30",
        "count": len(events),
        "counts": {
            "total": total_count,
            "approved": approved_count,
            "needs_review": needs_review_count,
        },
        "events": events,
    }


@router.post("/news-analysis/run")
async def run_macro_news_analysis_now(
    use_gemini: bool = True,
    fetch_live: bool = True,
    session: Session = Depends(get_db),
):
    """Trigger on-demand 3-tier official news crawl + Gemini JSON extraction + Supabase backtest validation."""
    from services.news.validator import run_daily_macro_news_pipeline_async

    run_date = max(get_effective_trading_date(), get_vn_now().date())
    return await run_daily_macro_news_pipeline_async(
        session=session,
        as_of_date=run_date,
        use_gemini=use_gemini,
        fetch_live=fetch_live,
        index_to_rag=True,
    )
