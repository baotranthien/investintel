from datetime import date, datetime
import pytest

from database.models import AnalystAlert, AnalystAutomationJob, AnalystBrief, Asset, WatchlistItem
from services.ai.analyst import AIAnalyst
from services.ai.automation import AnalystAutomationService
from services.ai.scheduler import _claim_job, _finish_job, run_analyst_automation_cycle


def test_daily_brief_generates_structured_sections_and_claim_types(db_session):
    service = AnalystAutomationService(session=db_session)
    context = {
        "market": {"status": "AVAILABLE", "market_regime": "BULLISH"},
        "macro": {"status": "AVAILABLE", "regions": [{"name": "VIETNAM"}]},
        "events": [{"title": "FPT dividend", "source": "official"}],
        "portfolio": {"status": "AVAILABLE", "items": [{"symbol": "FPT", "weight": 0.35}]},
        "evidence": [{
            "claim_type": "FACT",
            "responsible_module": "market",
            "metric": "regime",
            "value": "BULLISH",
            "source": "official_market",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
            "publication_date": "2026-10-01",
            "observation_date": "2026-10-01",
        }],
    }

    result = service.generate_brief("DAILY", "FPT", date(2026, 10, 1), context)
    assert result["brief_type"] == "DAILY"
    assert result["status"] == "AVAILABLE"
    assert "market" in result["sections"]
    assert any(item["claim_type"] in {"FACT", "MODEL_OUTPUT", "INTERPRETATION"} for item in result["claims"])
    assert any("regime" in item["text"] and "BULLISH" in item["text"] for item in result["claims"])
    assert result["uncertainty"] == []


def test_snapshot_change_detection_detects_relevant_changes():
    service = AnalystAutomationService(session=None)
    previous = {"portfolio": {"allocation": {"FPT": 0.2, "VCB": 0.8}}, "opportunity": {"score": 0.51}}
    current = {"portfolio": {"allocation": {"FPT": 0.35, "VCB": 0.65}}, "opportunity": {"score": 0.51}}

    result = service.detect_snapshot_changes(previous, current)
    assert "portfolio.allocation.FPT" in result
    assert "opportunity.score" not in result


def test_thesis_monitor_requires_evidence_before_updating(db_session):
    asset = Asset(symbol="TESTFPT", name="FPT", asset_type="STOCK", exchange="HOSE", sector="IT")
    db_session.add(asset)
    db_session.flush()
    item = WatchlistItem(asset_id=asset.id, thesis="Hold FPT for quality.", invalidation="Revenue weakens materially.", last_reviewed_at=datetime.utcnow())
    db_session.add(item)
    db_session.flush()

    service = AnalystAutomationService(session=db_session)
    result = service.monitor_thesis(item, evidence=[], contradicting_evidence=[], catalysts=["earnings"], invalidation="Revenue weakens materially.", confidence=0.8)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert item.thesis == "Hold FPT for quality."

    updated = service.monitor_thesis(
        item,
        evidence=[{"source": "official", "text": "FPT publishes stronger cash generation"}],
        contradicting_evidence=[],
        catalysts=["earnings"],
        invalidation="Revenue weakens materially.",
        confidence=0.8,
    )
    assert updated["status"] == "REVIEWED"
    assert updated["thesis"] == "Hold FPT for quality."
    assert updated["updated"] is False
    assert item.last_reviewed_at is not None


def test_alert_evaluation_only_emits_source_backed_changes_and_deduplicates():
    service = AnalystAutomationService(session=None)
    alerts = service.evaluate_alerts(
        {
            "valuation": {"status": "AVAILABLE", "score": 0.8, "source": "filing"},
            "risk": {"status": "AVAILABLE", "score": 0.6, "source": "risk_model"},
            "opportunity": {"status": "AVAILABLE", "score": 0.7, "source": "market_feed"},
        },
        previous={
            "valuation": {"status": "AVAILABLE", "score": 0.7, "source": "filing"},
            "risk": {"status": "AVAILABLE", "score": 0.6, "source": "risk_model"},
            "opportunity": {"status": "AVAILABLE", "score": 0.7, "source": "market_feed"},
        },
        evidence=[{"id": "E001", "source": "filing"}],
        prior_alerts=[],
    )
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "valuation_change"
    assert alerts[0]["evidence"]
    assert service.evaluate_alerts(
        {
            "valuation": {"status": "AVAILABLE", "score": 0.8, "source": "filing"},
        },
        previous={"valuation": {"status": "AVAILABLE", "score": 0.7, "source": "filing"}},
        evidence=[{"id": "E001", "source": "official"}],
        prior_alerts=alerts,
    ) == []


def test_alert_evaluation_ignores_unchanged_or_unverified_values():
    service = AnalystAutomationService(session=None)
    alerts = service.evaluate_alerts(
        {"valuation": {"status": "AVAILABLE", "score": 0.8}},
        previous={"valuation": {"status": "AVAILABLE", "score": 0.7}},
        evidence=[],
    )
    assert alerts == []


def test_persist_brief_is_idempotent(db_session):
    service = AnalystAutomationService(session=db_session)
    payload = {"brief_type": "DAILY", "status": "AVAILABLE", "claims": []}

    first = service.persist_brief("DAILY", date(2026, 10, 1), payload, idempotency_key="brief:DAILY:2026-10-01")
    second = service.persist_brief("DAILY", date(2026, 10, 1), {**payload, "status": "PARTIAL"}, idempotency_key="brief:DAILY:2026-10-01")

    assert first.id == second.id
    assert second.status == "AVAILABLE"


def test_missing_or_stale_evidence_returns_insufficient_data():
    service = AnalystAutomationService(session=None)
    result = service.generate_brief(
        "MONTHLY",
        "FPT",
        date(2026, 10, 1),
        {
            "evidence": [{
                "claim_type": "UNCERTAINTY",
                "responsible_module": "portfolio",
                "source": None,
                "data_origin": "SEEDED_OR_UNTRACED",
                "freshness": "STALE",
                "publication_date": "2026-10-01",
                "observation_date": "2026-10-01",
            }],
        },
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["uncertainty"]


import asyncio


def test_ai_analyst_brief_methods_accept_as_of_contract(db_session):
    analyst = AIAnalyst()
    target_date = date(2026, 9, 30)

    daily = asyncio.run(analyst.generate_daily_brief(db_session, as_of=target_date))
    assert str(daily["as_of_date"]) == "2026-09-30"

    weekly = asyncio.run(analyst.generate_weekly_brief(db_session, as_of=target_date))
    assert str(weekly["as_of_date"]) == "2026-09-30"

    monthly = asyncio.run(analyst.generate_monthly_brief(db_session, as_of=target_date))
    assert str(monthly["as_of_date"]) == "2026-09-30"


def test_scheduler_claim_job_concurrency_and_retry(db_session):
    key = "test:job:concurrency:2026-10-01"
    # First claim succeeds and marks RUNNING
    job1 = _claim_job(db_session, "TEST_JOB", key)
    assert job1 is not None
    assert job1.status == "RUNNING"

    # Immediate second claim returns None (prevents concurrent duplicate run)
    job2 = _claim_job(db_session, "TEST_JOB", key)
    assert job2 is None

    # If marked FAILED, retry is permitted
    _finish_job(db_session, job1, error="Simulated network failure", status="FAILED")
    assert job1.status == "FAILED"

    job_retry = _claim_job(db_session, "TEST_JOB", key)
    assert job_retry is not None
    assert job_retry.id == job1.id
    assert job_retry.status == "RUNNING"

    # If marked SUCCESS, subsequent claims return None (idempotent skip)
    _finish_job(db_session, job_retry, result={"ok": True}, status="SUCCESS")
    assert job_retry.status == "SUCCESS"

    job_done = _claim_job(db_session, "TEST_JOB", key)
    assert job_done is None


def test_scheduler_cycle_runs_and_persists_briefs_and_jobs(db_session):
    # Monday 2026-10-05 triggers DAILY + WEEKLY briefs
    simulated_date = date(2026, 10, 5)
    results = asyncio.run(run_analyst_automation_cycle(
        session_factory=lambda: db_session,
        as_of=simulated_date,
    ))
    assert len(results) >= 2
    # Verify daily brief was processed
    daily_res = next(r for r in results if "DAILY" in r["job_key"])
    assert daily_res["status"] == "SUCCESS"

    # Verify second run skips already successful jobs (idempotency)
    second_results = asyncio.run(run_analyst_automation_cycle(
        session_factory=lambda: db_session,
        as_of=simulated_date,
    ))
    assert all(r["status"] == "SKIPPED" for r in second_results)


def test_automation_api_endpoints(db_session):
    from fastapi.testclient import TestClient
    from apps.api.main import app
    from database.connection import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # 1. Stored brief list and detail
        service = AnalystAutomationService(session=db_session)
        brief = service.persist_brief(
            "DAILY",
            date(2026, 10, 1),
            {"brief_type": "DAILY", "status": "AVAILABLE", "claims": []},
            idempotency_key="test:api:brief:daily:2026-10-01",
        )

        resp = client.get("/api/v1/automation/briefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(b["id"] == brief.id for b in data["items"])

        resp_detail = client.get(f"/api/v1/automation/briefs/{brief.id}")
        assert resp_detail.status_code == 200
        assert resp_detail.json()["idempotency_key"] == "test:api:brief:daily:2026-10-01"

        resp_not_found = client.get("/api/v1/automation/briefs/999999")
        assert resp_not_found.status_code == 404

        # 2. Stored alert list and detail
        alert = AnalystAlert(
            alert_id="alert-test-12345",
            symbol="HPG",
            kind="valuation_change",
            status="OPEN",
            payload={"summary": "Valuation changed"},
        )
        db_session.add(alert)
        db_session.commit()

        resp_alerts = client.get("/api/v1/automation/alerts?symbol=HPG")
        assert resp_alerts.status_code == 200
        alerts_data = resp_alerts.json()
        assert alerts_data["total"] >= 1
        assert alerts_data["items"][0]["alert_id"] == "alert-test-12345"

        resp_alert_id = client.get("/api/v1/automation/alerts/alert-test-12345")
        assert resp_alert_id.status_code == 200
        assert resp_alert_id.json()["symbol"] == "HPG"

        # 3. AI router brief endpoints accept as_of_date
        post_brief = client.post("/api/v1/ai/daily-brief", json={"as_of_date": "2026-10-01"})
        assert post_brief.status_code == 200
        assert post_brief.json()["brief_type"] == "DAILY"

        # 4. Jobs list endpoint
        resp_jobs = client.get("/api/v1/automation/jobs")
        assert resp_jobs.status_code == 200
        assert "items" in resp_jobs.json()
    finally:
        app.dependency_overrides.clear()

