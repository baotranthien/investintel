from fastapi import APIRouter
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.events.engine import EventEngine

router = APIRouter(prefix="/api/v1/events", tags=["events"])

@router.get("")
def get_all_events(symbol: Optional[str] = None):
    """Returns recent macroscopic, geopolitical, or company-specific events."""
    return {"count": len(EventEngine.get_recent_events(symbol)), "events": EventEngine.get_recent_events(symbol)}
