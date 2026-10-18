"""
AI Router — Phase 5 endpoints.

Endpoints:
  GET  /api/v1/ai/status           — Ollama provider status (real GPU detection)
  POST /api/v1/ai/daily-brief      — Daily market intelligence brief
  POST /api/v1/ai/weekly-brief     — Weekly market intelligence brief
  POST /api/v1/ai/monthly-brief    — Monthly market intelligence brief
  POST /api/v1/ai/stock-analysis   — Deep-dive single stock research report
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.connection import get_db
from services.ai.analyst import AIAnalyst
from services.ai.providers import AIProviderError, OllamaProvider
from services.ai.evaluation import AIEvaluationFramework
from services.ai.schemas import AIChatRequest, AIChatResponse

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
analyst = AIAnalyst()


class BriefRequest(BaseModel):
    as_of_date: date | None = None


class StockAnalysisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    as_of_date: date | None = None


@router.get("/status")
def get_ai_status():
    """Returns the AI Gateway status including all configured providers, failover state, and GPU detection."""
    from services.ai.gateway import AIGateway
    gateway = AIGateway()
    return gateway.status()


@router.get("/eval")
def run_ai_evaluation(session: Session = Depends(get_db)):
    """
    Runs the deterministic AI Evaluation Framework.
    Tests tool schema integrity, data grounding, guard coverage, and score consistency.
    No LLM calls — all tests are deterministic Python checks.
    """
    framework = AIEvaluationFramework(session=session)
    return framework.run_all()


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_analyst(payload: AIChatRequest, session: Session = Depends(get_db)):
    try:
        return await analyst.answer_question(
            payload.question,
            session=session,
            symbol=payload.symbol,
            as_of=payload.as_of_date,
            tool_names=payload.tool_names,
        )
    except AIProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/daily-brief")
async def generate_daily_brief(
    req: BriefRequest = BriefRequest(),
    as_of: date | None = None,
    session: Session = Depends(get_db),
):
    """Generates the comprehensive Daily Market Intelligence brief."""
    target_date = req.as_of_date or as_of
    try:
        analysis = await analyst.generate_daily_brief(session, as_of=target_date)
    except AIProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": analysis["status"], "brief_type": "DAILY", "as_of_date": target_date or analysis.get("as_of_date"), "content": analysis["answer"], "analysis": analysis}


@router.post("/weekly-brief")
async def generate_weekly_brief(
    req: BriefRequest = BriefRequest(),
    as_of: date | None = None,
    session: Session = Depends(get_db),
):
    """
    Generates Weekly Market Intelligence Brief.
    Covers: 5-day regime/macro context, watchlist signals, weekly events, forward risks.
    """
    target_date = req.as_of_date or as_of
    try:
        analysis = await analyst.generate_weekly_brief(session, as_of=target_date)
    except AIProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": analysis["status"], "brief_type": "WEEKLY", "as_of_date": target_date or analysis.get("as_of_date"), "content": analysis["answer"], "analysis": analysis}


@router.post("/monthly-brief")
async def generate_monthly_brief(
    req: BriefRequest = BriefRequest(),
    as_of: date | None = None,
    session: Session = Depends(get_db),
):
    """
    Generates Monthly Market Intelligence Brief.
    Covers: macro trends, sector rotation, earnings cycle summary, monthly outlook.
    Uses REASONING model for deeper analysis.
    """
    target_date = req.as_of_date or as_of
    try:
        analysis = await analyst.generate_monthly_brief(session, as_of=target_date)
    except AIProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": analysis["status"], "brief_type": "MONTHLY", "as_of_date": target_date or analysis.get("as_of_date"), "content": analysis["answer"], "analysis": analysis}


@router.post("/stock-analysis")
async def analyze_stock(req: StockAnalysisRequest, session: Session = Depends(get_db)):
    """Generates a deep-dive AI Stock Research Report."""
    try:
        analysis = await analyst.analyze_stock(req.symbol, session, req.as_of_date)
    except AIProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": analysis["status"], "symbol": req.symbol.upper(), "brief_type": "STOCK_ANALYSIS", "content": analysis["answer"], "analysis": analysis}
