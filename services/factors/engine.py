from typing import Dict, Any, List
from datetime import date
from .models import FactorScore, FactorProfile

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
        revenue_growth = fundamentals.get("revenue_growth", 0.10)
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
