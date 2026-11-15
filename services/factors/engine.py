from typing import Dict, Any, Optional
from datetime import date
from .models import FactorScore, FactorProfile


def _z_to_score(z: Optional[float], invert: bool = False) -> Optional[float]:
    """Map Winsorized industry Z-score (-2.5..+2.5) to bounded 0-100 score centered at 50."""
    if z is None:
        return None
    signed_z = -float(z) if invert else float(z)
    clipped = max(-2.5, min(2.5, signed_z))
    return round(50.0 + clipped * 18.0, 2)


class FactorEngine:
    @staticmethod
    def _normalize(value: float, min_val: float, max_val: float) -> float:
        """Winsorized normalization to 0-100 scale"""
        if max_val == min_val:
            return 50.0
        val = max(min_val, min(max_val, value))
        return ((val - min_val) / (max_val - min_val)) * 100

    def calculate_profile(self, symbol: str, fundamentals: Dict[str, Any], as_of: date) -> FactorProfile:
        # In a real implementation, we would extract raw metrics, adjust for sector, and map to percentiles.
        # This is a structural demonstration.
        
        roe = fundamentals.get("roe", 0.15)
        if roe is not None and abs(roe) > 1.0:
            roe = roe / 100.0
        revenue_growth = fundamentals.get("revenue_growth", 0.10)
        if revenue_growth is not None and abs(revenue_growth) > 1.0:
            revenue_growth = revenue_growth / 100.0
        pe = fundamentals.get("pe", 15.0)
        div_yield = fundamentals.get("dividend_yield", 0.03)
        momentum_6m = fundamentals.get("momentum_6m", 0.05)
        beta = fundamentals.get("beta", 1.0)
        
        # 1. Quality Factor
        # High ROE, stable margins -> High Quality
        quality_score = self._normalize(roe, 0.05, 0.25)
        quality = FactorScore(
            name="Quality", 
            score=quality_score, 
            drivers=["High ROE" if roe > 0.15 else "Moderate ROE"]
        )
        
        # 2. Growth Factor
        growth_score = self._normalize(revenue_growth, 0.0, 0.30)
        growth = FactorScore(
            name="Growth", 
            score=growth_score,
            drivers=["Strong Revenue Growth" if revenue_growth > 0.15 else "Stable Growth"]
        )
        
        # 3. Value Factor
        # Lower P/E -> Higher Value Score
        value_score = 100 - self._normalize(pe, 5.0, 30.0)
        value = FactorScore(
            name="Value",
            score=value_score,
            drivers=["Attractive P/E Multiple" if pe < 12 else "Premium Valuation"]
        )
        
        # 4. Dividend Factor
        div_score = self._normalize(div_yield, 0.0, 0.08)
        dividend = FactorScore(
            name="Dividend",
            score=div_score,
            drivers=["High Dividend Yield" if div_yield > 0.05 else "Low Dividend Yield"]
        )
        
        # 5. Momentum Factor
        mom_score = self._normalize(momentum_6m, -0.20, 0.40)
        momentum = FactorScore(
            name="Momentum",
            score=mom_score,
            drivers=["Positive 6M Trend" if momentum_6m > 0 else "Negative Trend"]
        )
        
        # 6. Defensive Factor
        # Lower beta -> Higher defensive score
        def_score = 100 - self._normalize(beta, 0.5, 1.5)
        defensive = FactorScore(
            name="Defensive",
            score=def_score,
            drivers=["Low Market Beta" if beta < 0.9 else "High Volatility"]
        )
        
        # 7. Cyclical Factor
        # Higher beta -> Higher cyclical score
        cyc_score = self._normalize(beta, 0.8, 1.8)
        cyclical = FactorScore(
            name="Cyclical",
            score=cyc_score,
            drivers=["Economically Sensitive" if beta > 1.2 else "Stable Demand"]
        )
        
        # Factor Conflicts
        conflicts = []
        if quality_score > 80 and value_score < 30:
            conflicts.append("High Quality / Low Value (Expensive Quality)")
        if growth_score > 80 and value_score > 80:
            conflicts.append("High Growth / High Value (Rare Opportunity or Value Trap)")
            
        return FactorProfile(
            symbol=symbol,
            as_of=as_of,
            quality=quality,
            growth=growth,
            value=value,
            dividend=dividend,
            momentum=momentum,
            defensive=defensive,
            cyclical=cyclical,
            conflicts=conflicts
        )

    def calculate_cross_sectional_profile(
        self,
        symbol: str,
        as_of: date,
        session: Any = None,
        fundamentals: Optional[Dict[str, Any]] = None,
    ) -> FactorProfile:
        """
        Compute sector-relative factor scores using Postgres `rpc_get_cross_sectional_features`
        (Industry Z-scores) when running on PostgreSQL, falling back cleanly to `calculate_profile`
        on SQLite or missing peer distributions.
        """
        base_profile = self.calculate_profile(symbol, fundamentals or {}, as_of)
        if session is None:
            return base_profile

        try:
            from services.common.supabase_rpc import call_pg_rpc, is_postgres_session

            if not is_postgres_session(session):
                return base_profile

            rows = call_pg_rpc(
                session,
                "rpc_get_cross_sectional_features",
                {"p_as_of": as_of, "p_symbol": symbol.upper()},
            )
            if not isinstance(rows, list) or not rows:
                return base_profile

            row = rows[0]
            peer_n = int(row.get("peer_count") or 0)
            if peer_n < 2:
                return base_profile

            sector_name = row.get("sector") or "GENERAL"

            # Sector-normalized Quality (Z-score blend of ROE, Net Margin, low Leverage)
            z_qual_parts = [z for z in (row.get("z_roe"), row.get("z_net_margin"), (-float(row["z_de_ratio"]) if row.get("z_de_ratio") is not None else None)) if z is not None]
            if z_qual_parts:
                z_q = sum(float(z) for z in z_qual_parts) / len(z_qual_parts)
                q_score = _z_to_score(z_q)
                if q_score is not None:
                    base_profile.quality.score = q_score
                    base_profile.quality.drivers.append(
                        f"Sector Z-Score ({sector_name}, N={peer_n}): ROE={row.get('roe')}% vs peer mean {row.get('sector_mean_roe')}%"
                    )

            # Sector-normalized Value (low Z_PE & low Z_PB -> higher Value score)
            z_val_parts = [z for z in (row.get("z_pe"), row.get("z_pb")) if z is not None]
            if z_val_parts:
                z_v = sum(float(z) for z in z_val_parts) / len(z_val_parts)
                v_score = _z_to_score(z_v, invert=True)
                if v_score is not None:
                    base_profile.value.score = v_score
                    base_profile.value.drivers.append(
                        f"Sector Z-Score ({sector_name}, N={peer_n}): P/E={row.get('pe')}x vs mean {row.get('sector_mean_pe')}x, P/B={row.get('pb')}x vs mean {row.get('sector_mean_pb')}x"
                    )

            # Sector-normalized Momentum (Z_20D + Z_60D)
            z_mom_parts = [z for z in (row.get("z_mom_20d"), row.get("z_mom_60d")) if z is not None]
            if z_mom_parts:
                z_m = sum(float(z) for z in z_mom_parts) / len(z_mom_parts)
                m_score = _z_to_score(z_m)
                if m_score is not None:
                    base_profile.momentum.score = m_score
                    base_profile.momentum.drivers.append(
                        f"Sector Z-Score 20D/60D ({sector_name}): {row.get('mom_20d')}% / {row.get('mom_60d')}%"
                    )

            base_profile.conflicts = []
            if base_profile.quality.score > 70 and base_profile.value.score < 35:
                base_profile.conflicts.append("Sector Quality Premium (Expensive vs Sector Peers)")
            if base_profile.quality.score > 65 and base_profile.value.score > 65:
                base_profile.conflicts.append("Sector Compounder Value (High Quality + Cheap vs Peers)")
        except Exception:
            pass
        return base_profile
