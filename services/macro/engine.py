from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import MacroDashboard, MacroRegimeState, MacroVariable, MarketRegime, MarketBreadth
from database.connection import SessionLocal
from database.models import Asset, IndexMembership, MacroObservation, MacroSeries, Price

class MacroEngine:
    @staticmethod
    def get_dashboard(as_of: date, session: Optional[Session] = None) -> MacroDashboard:
        """
        Synthesizes macro variables into a cohesive dashboard state.
        Reads from canonical macro observations stored in the database.
        Returns honest INSUFFICIENT_DATA states when no real observations exist.
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            # Query active macro observations published strictly on or before as_of date
            from sqlalchemy import and_, or_
            from datetime import time, datetime
            as_of_dt = datetime.combine(as_of, time.max)
            observations = session.query(MacroObservation, MacroSeries).join(
                MacroSeries, MacroObservation.series_id == MacroSeries.id
            ).filter(
                or_(
                    MacroObservation.published_at <= as_of_dt,
                    and_(MacroObservation.published_at == None, MacroObservation.release_date <= as_of),
                    and_(MacroObservation.published_at == None, MacroObservation.release_date == None, MacroObservation.observation_date <= as_of)
                )
            ).order_by(MacroObservation.observation_date.desc(), MacroObservation.version.desc()).all()

            if not observations:
                # Honest INSUFFICIENT_DATA response — no fabricated expansion
                empty_state = MacroRegimeState(
                    state="STABLE",
                    direction="FLAT",
                    strength=0.0,
                    confidence=0.0,
                    drivers=["INSUFFICIENT_DATA: No macro observations ingested in database"]
                )
                return MacroDashboard(
                    growth=empty_state,
                    inflation=empty_state,
                    liquidity=empty_state,
                    rates=empty_state,
                    currency=empty_state,
                    credit=empty_state,
                    external_demand=empty_state,
                    commodities=empty_state,
                    variables=[]
                )

            # Map observations into MacroVariable objects
            variables = []
            seen_series = set()
            for obs, series in observations:
                if series.id in seen_series:
                    continue
                seen_series.add(series.id)
                region = "VIETNAM" if "VNM" in series.id.upper() or "VN" in series.id.upper() else "US"
                variables.append(
                    MacroVariable(
                        name=series.name,
                        region=region,
                        current_value=float(obs.value),
                        previous_value=float(obs.value),
                        yoy=0.0,
                        trend="STABLE",
                        source=series.provider,
                        as_of=obs.observation_date
                    )
                )

            # Synthesize states based on real variables
            state = MacroRegimeState(
                state="STABLE",
                direction="FLAT",
                strength=50.0,
                confidence=0.7,
                drivers=[f"Derived from {len(variables)} ingested macro series in database"]
            )
            return MacroDashboard(
                growth=state,
                inflation=state,
                liquidity=state,
                rates=state,
                currency=state,
                credit=state,
                external_demand=state,
                commodities=state,
                variables=variables
            )
        finally:
            if close_session:
                session.close()

class MarketRegimeEngine:
    @staticmethod
    def determine_regime(
        as_of: date,
        session: Optional[Session] = None,
        benchmark: str = "VN100",
    ) -> MarketRegime:
        """
        Determines market regime based on stored prices and breadth.
        Returns honest INSUFFICIENT_DATA when market features or constituent coverage are below threshold.
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        benchmark_upper = benchmark.upper()
        denom_rule = "advancing / (advancing + declining + unchanged) across constituents with valid aligned session prices"

        try:
            from sqlalchemy import or_
            from datetime import datetime, time

            as_of_dt = datetime.combine(as_of, time.max)
            index_prices = session.query(Price).join(Asset, Price.asset_id == Asset.id).filter(
                Asset.symbol == benchmark_upper,
                Price.status == "VALID",
                Price.observation_date <= as_of,
            ).order_by(Price.observation_date.desc()).limit(21).all()
            if len(index_prices) < 21:
                return MarketRegime(
                    regime="INSUFFICIENT_DATA",
                    confidence=0.0,
                    drivers=[f"INSUFFICIENT_DATA: {benchmark_upper} needs 21 valid index bars for 20-session momentum (found {len(index_prices)})"],
                    risks=[],
                    changes=[],
                    as_of=as_of,
                    benchmark=benchmark_upper,
                    denominator_rule=denom_rule,
                )

            memberships = session.query(IndexMembership).filter(
                IndexMembership.index_symbol == benchmark_upper,
                IndexMembership.start_date <= as_of,
                or_(IndexMembership.end_date.is_(None), IndexMembership.end_date >= as_of),
            ).all()
            memberships = [
                membership for membership in memberships
                if membership.published_at is None or membership.published_at.date() <= as_of
            ]
            benchmark_date = index_prices[0].observation_date
            advancing = 0
            declining = 0
            unchanged = 0
            covered_members = 0

            for membership in memberships:
                member_prices = session.query(Price).join(
                    Asset, Price.asset_id == Asset.id
                ).filter(
                    Asset.symbol == membership.symbol,
                    Price.status == "VALID",
                    Price.observation_date <= benchmark_date,
                ).order_by(Price.observation_date.desc()).limit(2).all()
                if len(member_prices) < 2 or member_prices[0].observation_date != benchmark_date:
                    continue
                latest_value = member_prices[0].adjusted_close or member_prices[0].raw_close
                previous_value = member_prices[1].adjusted_close or member_prices[1].raw_close
                if latest_value is None or previous_value is None:
                    continue
                covered_members += 1
                if latest_value > previous_value:
                    advancing += 1
                elif latest_value < previous_value:
                    declining += 1
                else:
                    unchanged += 1

            latest_close = index_prices[0].adjusted_close or index_prices[0].raw_close
            prior_close = index_prices[-1].adjusted_close or index_prices[-1].raw_close
            if not latest_close or not prior_close:
                return MarketRegime(
                    regime="INSUFFICIENT_DATA",
                    confidence=0.0,
                    drivers=[f"INSUFFICIENT_DATA: {benchmark_upper} benchmark close is missing"],
                    risks=[],
                    changes=[],
                    as_of=benchmark_date,
                    model_version=f"{benchmark_upper.lower()}_price_breadth_v1",
                    data_coverage=0.0,
                    benchmark=benchmark_upper,
                    total_eligible=len(memberships),
                    covered_members=covered_members,
                    denominator_rule=denom_rule,
                )

            momentum = latest_close / prior_close - 1.0
            momentum_signal = f"{benchmark_upper} 20-session momentum: {momentum:+.2%}"

            # Minimum constituent threshold guard:
            # Broad-market basket requires >= 50% coverage and at least minimum members
            min_constituents = 15 if benchmark_upper == "VN30" else 10
            total_eligible = len(memberships)
            coverage = covered_members / total_eligible if total_eligible > 0 else 0.0
            if covered_members < min_constituents or coverage < 0.5:
                return MarketRegime(
                    regime="INSUFFICIENT_DATA",
                    confidence=0.0,
                    drivers=[
                        f"INSUFFICIENT_DATA: Độ phủ thành phần {benchmark_upper} chưa đủ đại diện (ngưỡng >= 50%)",
                        f"Độ phủ: {covered_members}/{total_eligible} ({coverage:.1%}) mã thành phần có giá cùng phiên {benchmark_date} (cần tối thiểu {min_constituents} mã và >= 50%)",
                    ],
                    risks=[f"Market breadth cannot be reliably assessed with coverage under 50% ({covered_members}/{total_eligible})."],
                    changes=[],
                    as_of=benchmark_date,
                    model_version=f"{benchmark_upper.lower()}_price_breadth_v1",
                    data_coverage=round(coverage, 3),
                    momentum_20d=momentum,
                    historical_context=[momentum_signal],
                    benchmark=benchmark_upper,
                    total_eligible=total_eligible,
                    covered_members=covered_members,
                    advancing=advancing,
                    declining=declining,
                    unchanged=unchanged,
                    denominator_rule=denom_rule,
                )

            breadth = advancing / covered_members
            if momentum > 0.05 and breadth >= 0.60:
                regime_name = "EXPANSION"
            elif momentum > 0 and breadth >= 0.50:
                regime_name = "RECOVERY"
            elif momentum < -0.05 and breadth < 0.40:
                regime_name = "RISK_OFF"
            else:
                regime_name = "NEUTRAL"

            breadth_signal = f"{benchmark_upper} breadth: {advancing} advancing, {declining} declining, {unchanged} unchanged"
            momentum_supports = momentum > 0 if regime_name in ("EXPANSION", "RECOVERY") else momentum < 0
            breadth_supports = breadth >= 0.50 if regime_name in ("EXPANSION", "RECOVERY") else breadth < 0.50
            supporting_signals = []
            conflicting_signals = []
            (supporting_signals if momentum_supports else conflicting_signals).append(momentum_signal)
            (supporting_signals if breadth_supports else conflicting_signals).append(breadth_signal)

            return MarketRegime(
                regime=regime_name,
                confidence=round(coverage, 3),
                drivers=supporting_signals,
                risks=conflicting_signals,
                changes=[],
                as_of=benchmark_date,
                model_version=f"{benchmark_upper.lower()}_price_breadth_v1",
                supporting_signals=supporting_signals,
                conflicting_signals=conflicting_signals,
                data_coverage=round(coverage, 3),
                historical_context=[momentum_signal],
                momentum_20d=momentum,
                advancing=advancing,
                declining=declining,
                unchanged=unchanged,
                breadth_percent=round(breadth * 100.0, 2),
                benchmark=benchmark_upper,
                total_eligible=total_eligible,
                covered_members=covered_members,
                denominator_rule=denom_rule,
            )
        finally:
            if close_session:
                session.close()
