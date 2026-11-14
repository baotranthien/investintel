"""
Dual Price Series & Corporate Action Total-Return Adjustment Engine.

Separates nominal traded market prices (`raw_close` — used for spot valuation
ratios P/E, P/B, dividend yield) from dividend- and split-adjusted total-return
prices (`adjusted_close` — used for historical return calculation & backtesting).

Rules:
1. Never overwrites `raw_close`.
2. Strictly enforces Point-in-Time cutoff (ex_date/action_date <= as_of).
3. Uses standard backward cumulative adjustment multipliers from latest close = 1.0x.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional, Sequence
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Asset, CorporateAction, Price
from services.fundamentals.shares import _coerce_date, parse_corporate_action_parameters


@dataclass
class AdjustedPriceBar:
    observation_date: date
    raw_close: float
    adjusted_close: float
    adjustment_factor: float
    raw_open: Optional[float] = None
    adjusted_open: Optional[float] = None
    raw_high: Optional[float] = None
    adjusted_high: Optional[float] = None
    raw_low: Optional[float] = None
    adjusted_low: Optional[float] = None
    volume: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_date": self.observation_date.isoformat(),
            "raw_close": round(self.raw_close, 4),
            "adjusted_close": round(self.adjusted_close, 4),
            "adjustment_factor": round(self.adjustment_factor, 8),
            "volume": self.volume,
        }


@dataclass
class PriceSeriesAudit:
    symbol: str
    total_bars: int
    dual_series_bars: int
    raw_only_bars: int
    unadjusted_action_gaps: list[dict[str, Any]] = field(default_factory=list)
    applied_actions_count: int = 0
    status: str = "MISSING_PRICES"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "total_bars": self.total_bars,
            "dual_series_bars": self.dual_series_bars,
            "raw_only_bars": self.raw_only_bars,
            "unadjusted_action_gaps": self.unadjusted_action_gaps,
            "applied_actions_count": self.applied_actions_count,
            "status": self.status,
        }


class PriceAdjustmentEngine:
    """Computes backward cumulative total-return price adjustments without mutating raw quotes."""

    @staticmethod
    def _extract_bar_fields(bar: Any) -> dict[str, Any]:
        if isinstance(bar, dict):
            obs = _coerce_date(bar.get("observation_date"))
            raw_c = bar.get("raw_close") if bar.get("raw_close") is not None else bar.get("close")
            return {
                "observation_date": obs,
                "raw_close": float(raw_c) if raw_c is not None else None,
                "adjusted_close": float(bar["adjusted_close"]) if bar.get("adjusted_close") is not None else None,
                "adjustment_factor": float(bar["adjustment_factor"]) if bar.get("adjustment_factor") is not None else None,
                "raw_open": float(bar["raw_open"]) if bar.get("raw_open") is not None else (float(bar["open"]) if bar.get("open") is not None else None),
                "raw_high": float(bar["raw_high"]) if bar.get("raw_high") is not None else (float(bar["high"]) if bar.get("high") is not None else None),
                "raw_low": float(bar["raw_low"]) if bar.get("raw_low") is not None else (float(bar["low"]) if bar.get("low") is not None else None),
                "volume": float(bar["volume"]) if bar.get("volume") is not None else None,
            }
        return {
            "observation_date": _coerce_date(getattr(bar, "observation_date", None)),
            "raw_close": float(getattr(bar, "raw_close")) if getattr(bar, "raw_close", None) is not None else None,
            "adjusted_close": float(getattr(bar, "adjusted_close")) if getattr(bar, "adjusted_close", None) is not None else None,
            "adjustment_factor": float(getattr(bar, "adjustment_factor")) if getattr(bar, "adjustment_factor", None) is not None else None,
            "raw_open": float(getattr(bar, "raw_open")) if getattr(bar, "raw_open", None) is not None else None,
            "raw_high": float(getattr(bar, "raw_high")) if getattr(bar, "raw_high", None) is not None else None,
            "raw_low": float(getattr(bar, "raw_low")) if getattr(bar, "raw_low", None) is not None else None,
            "volume": float(getattr(bar, "volume")) if getattr(bar, "volume", None) is not None else None,
        }

    @classmethod
    def compute_adjusted_series(
        cls,
        raw_prices: Sequence[Any],
        corporate_actions: Sequence[dict[str, Any] | CorporateAction],
        *,
        as_of: Optional[date] = None,
        include_cash_dividends: bool = True,
    ) -> tuple[list[AdjustedPriceBar], list[dict[str, Any]]]:
        """
        Computes backward cumulative `adjustment_factor` and `adjusted_close` for each bar
        using strictly Point-in-Time CorporateAction records (effective_date <= as_of).
        Returns (adjusted_bars, applied_events).
        """
        normalized_bars: list[dict[str, Any]] = []
        for row in raw_prices:
            fields = cls._extract_bar_fields(row)
            obs = fields["observation_date"]
            raw_c = fields["raw_close"]
            if obs is None or raw_c is None or raw_c <= 0:
                continue
            if as_of is not None and obs > as_of:
                continue
            normalized_bars.append(fields)

        normalized_bars.sort(key=lambda b: b["observation_date"])
        if not normalized_bars:
            return [], []

        obs_dates = [b["observation_date"] for b in normalized_bars]

        # Normalize actions
        action_dicts: list[dict[str, Any]] = []
        for ca in corporate_actions:
            if isinstance(ca, dict):
                ca_d = ca
            else:
                ca_d = {
                    "action_date": ca.action_date,
                    "ex_date": ca.ex_date,
                    "action_type": ca.action_type,
                    "ratio": float(ca.ratio) if ca.ratio is not None else None,
                    "value": float(ca.value) if ca.value is not None else None,
                    "notes": ca.notes,
                    "source": ca.source,
                }
            parsed = parse_corporate_action_parameters(ca_d)
            eff = parsed["effective_date"]
            if eff is None:
                continue
            if as_of is not None and eff > as_of:
                continue
            action_dicts.append(parsed)

        action_dicts.sort(key=lambda a: a["effective_date"])

        # Compute per-event price multiplier f_e (< 1.0 when share count increases or cash is distributed)
        event_multipliers: list[tuple[date, float, dict[str, Any]]] = []
        for ev in action_dicts:
            eff = ev["effective_date"]
            atype = ev["action_type"]

            # Pre-ex-date bar close (latest trading session strictly before eff)
            idx = bisect_left(obs_dates, eff)
            pre_ex_close = normalized_bars[idx - 1]["raw_close"] if idx > 0 else None

            mult_price: Optional[float] = None
            if atype in ("STOCK_DIVIDEND", "BONUS_ISSUE", "STOCK_SPLIT", "REVERSE_SPLIT"):
                share_mult = ev.get("share_multiplier")
                if share_mult and share_mult > 0:
                    mult_price = 1.0 / float(share_mult)
            elif atype == "CASH_DIVIDEND" and include_cash_dividends:
                cash_d = ev.get("cash_dividend_per_share")
                if cash_d and cash_d > 0 and pre_ex_close and pre_ex_close > cash_d:
                    mult_price = (pre_ex_close - float(cash_d)) / pre_ex_close
            elif atype == "RIGHTS_ISSUE":
                r = ev.get("share_increment_ratio")
                p_sub = ev.get("subscription_price")
                if r and r > 0 and p_sub and pre_ex_close and 0 < p_sub < pre_ex_close:
                    p_ex = (pre_ex_close + float(r) * float(p_sub)) / (1.0 + float(r))
                    mult_price = p_ex / pre_ex_close

            if mult_price is not None and mult_price > 0 and abs(mult_price - 1.0) > 1e-8:
                meta = {
                    "effective_date": eff.isoformat(),
                    "action_type": atype,
                    "price_multiplier": round(mult_price, 8),
                    "pre_ex_close": pre_ex_close,
                    "source": ev.get("source"),
                }
                event_multipliers.append((eff, mult_price, meta))

        adjusted_bars: list[AdjustedPriceBar] = []
        for bar in normalized_bars:
            obs = bar["observation_date"]
            factor = 1.0
            for eff, mult_price, _ in event_multipliers:
                if obs < eff:
                    factor *= mult_price

            raw_c = bar["raw_close"]
            raw_o = bar["raw_open"]
            raw_h = bar["raw_high"]
            raw_l = bar["raw_low"]
            adjusted_bars.append(AdjustedPriceBar(
                observation_date=obs,
                raw_close=raw_c,
                adjusted_close=raw_c * factor,
                adjustment_factor=factor,
                raw_open=raw_o,
                adjusted_open=(raw_o * factor) if raw_o is not None else None,
                raw_high=raw_h,
                adjusted_high=(raw_h * factor) if raw_h is not None else None,
                raw_low=raw_l,
                adjusted_low=(raw_l * factor) if raw_l is not None else None,
                volume=bar["volume"],
            ))

        return adjusted_bars, [m for _, _, m in event_multipliers]

    @classmethod
    def audit_price_series(
        cls,
        symbol: str,
        raw_prices: Sequence[Any],
        corporate_actions: Sequence[dict[str, Any] | CorporateAction],
        *,
        as_of: Optional[date] = None,
    ) -> PriceSeriesAudit:
        """Detects unadjusted pre-ex-date price bars or missing dual-series separation."""
        sym = symbol.strip().upper()
        extracted = [cls._extract_bar_fields(b) for b in raw_prices]
        valid = [b for b in extracted if b["observation_date"] and b["raw_close"] and (as_of is None or b["observation_date"] <= as_of)]
        if not valid:
            return PriceSeriesAudit(symbol=sym, total_bars=0, dual_series_bars=0, raw_only_bars=0, status="MISSING_PRICES")

        expected_bars, applied_events = cls.compute_adjusted_series(valid, corporate_actions, as_of=as_of)
        expected_map = {b.observation_date: b for b in expected_bars}

        dual_cnt = 0
        raw_only_cnt = 0
        unadjusted_gaps: list[dict[str, Any]] = []

        for b in valid:
            obs = b["observation_date"]
            raw_c = b["raw_close"]
            adj_c = b["adjusted_close"]
            if adj_c is not None and adj_c > 0:
                dual_cnt += 1
            else:
                raw_only_cnt += 1

            exp = expected_map.get(obs)
            if exp and exp.adjustment_factor < 0.995:
                stored_ratio = (adj_c / raw_c) if (adj_c and raw_c > 0) else 1.0
                if abs(stored_ratio - exp.adjustment_factor) > 0.005:
                    unadjusted_gaps.append({
                        "observation_date": obs.isoformat(),
                        "raw_close": raw_c,
                        "stored_adjusted_close": adj_c,
                        "expected_adjusted_close": round(exp.adjusted_close, 2),
                        "expected_factor": round(exp.adjustment_factor, 6),
                    })

        status = "UNADJUSTED_ACTION_DETECTED" if unadjusted_gaps else ("CLEAN_DUAL_SERIES" if raw_only_cnt == 0 else "PARTIAL_ADJUSTED_SERIES")
        return PriceSeriesAudit(
            symbol=sym,
            total_bars=len(valid),
            dual_series_bars=dual_cnt,
            raw_only_bars=raw_only_cnt,
            unadjusted_action_gaps=unadjusted_gaps[:20],
            applied_actions_count=len(applied_events),
            status=status,
        )

    @classmethod
    def recompute_asset_adjusted_prices(
        cls,
        session: Session,
        symbol: str,
        *,
        as_of: Optional[date] = None,
        include_cash_dividends: bool = True,
        commit: bool = False,
    ) -> dict[str, Any]:
        """
        Recomputes `adjusted_close` and `adjustment_factor` for an asset's `Price` rows
        from its PIT `CorporateAction` history without ever mutating `raw_close`.
        """
        sym = symbol.strip().upper()
        asset = session.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            return {"status": "ASSET_NOT_FOUND", "symbol": sym, "updated_rows": 0}

        q_prices = session.query(Price).filter(Price.asset_id == asset.id, Price.status == "VALID")
        q_actions = session.query(CorporateAction).filter(CorporateAction.symbol == sym)
        if as_of:
            q_prices = q_prices.filter(Price.observation_date <= as_of)
            q_actions = q_actions.filter(func.coalesce(CorporateAction.ex_date, CorporateAction.action_date) <= as_of)

        rows = q_prices.order_by(Price.observation_date.asc()).all()
        actions = q_actions.order_by(func.coalesce(CorporateAction.ex_date, CorporateAction.action_date).asc()).all()

        computed, events = cls.compute_adjusted_series(
            rows, actions, as_of=as_of, include_cash_dividends=include_cash_dividends
        )
        comp_by_date = {b.observation_date: b for b in computed}

        updated = 0
        for row in rows:
            bar = comp_by_date.get(row.observation_date)
            if not bar:
                continue
            new_adj = round(bar.adjusted_close, 4)
            new_fac = round(bar.adjustment_factor, 8)
            if row.adjusted_close is None or abs(float(row.adjusted_close) - new_adj) > 1e-4 or row.adjustment_factor is None or abs(float(row.adjustment_factor) - new_fac) > 1e-6:
                row.adjusted_close = new_adj
                row.adjustment_factor = new_fac
                updated += 1

        if commit:
            session.commit()

        return {
            "status": "UPDATED" if updated > 0 else "UNCHANGED",
            "symbol": sym,
            "bars_evaluated": len(rows),
            "events_applied": events,
            "updated_rows": updated,
            "committed": commit,
        }

