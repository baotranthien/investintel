# -*- coding: utf-8 -*-
"""
Canonical Price Resolver — Single unified source of market price truth across InvestIntel.

Rules:
1. Strict observation_date scoping (observation_date <= as_of).
2. Explicit distinction between adjusted_close and raw_close (defaulting to adjusted).
3. Uniform classification: AVAILABLE, PARTIAL, STALE, NOT_VERIFIED.
4. Batch-resolution capability to eliminate N+1 queries in screener, peers, dashboard.
5. Guaranteed identical price across Valuation, Screener, Workspace, AI Analyst, API.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, List, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import Asset, Price


@dataclass
class CanonicalPrice:
    symbol: str
    asset_id: int
    observation_date: Optional[date]
    price: Optional[float]
    adjusted_close: Optional[float]
    raw_close: Optional[float]
    adjustment_factor: Optional[float]
    volume: Optional[float]
    status: str                 # AVAILABLE | PARTIAL | STALE | NOT_VERIFIED
    source: Optional[str]
    is_stale: bool
    data_origin: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "asset_id": self.asset_id,
            "observation_date": self.observation_date.isoformat() if self.observation_date else None,
            "price": self.price,
            "adjusted_close": self.adjusted_close,
            "raw_close": self.raw_close,
            "adjustment_factor": self.adjustment_factor,
            "volume": self.volume,
            "status": self.status,
            "source": self.source,
            "is_stale": self.is_stale,
            "data_origin": self.data_origin,
        }


class CanonicalPriceResolver:
    """
    Authoritative canonical price resolver.
    Guarantees deterministic, point-in-time compliant market close resolution.
    """

    @classmethod
    def resolve_price(
        cls,
        session: Session,
        symbol: str,
        as_of: Optional[date] = None,
        price_basis: Literal["ADJUSTED", "RAW"] = "ADJUSTED",
    ) -> CanonicalPrice:
        """
        Resolves canonical price for a single symbol at a given as_of date.
        """
        as_of = as_of or date.today()
        sym = symbol.strip().upper()
        asset = session.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            return CanonicalPrice(
                symbol=sym,
                asset_id=0,
                observation_date=None,
                price=None,
                adjusted_close=None,
                raw_close=None,
                adjustment_factor=None,
                volume=None,
                status="NOT_VERIFIED",
                source=None,
                is_stale=False,
                data_origin="ASSET_NOT_FOUND",
            )

        p = (
            session.query(Price)
            .filter(
                Price.asset_id == asset.id,
                Price.status == "VALID",
                Price.observation_date <= as_of,
            )
            .order_by(Price.observation_date.desc())
            .first()
        )

        return cls._build_canonical_price(asset.symbol, asset.id, p, as_of, price_basis)

    @classmethod
    def resolve_prices_batch(
        cls,
        session: Session,
        symbols: Optional[List[str]] = None,
        asset_ids: Optional[List[int]] = None,
        as_of: Optional[date] = None,
        price_basis: Literal["ADJUSTED", "RAW"] = "ADJUSTED",
    ) -> Dict[str, CanonicalPrice]:
        """
        Batch resolves canonical prices for multiple symbols in a single SQL query.
        """
        as_of = as_of or date.today()
        asset_query = session.query(Asset).filter(Asset.status == "ACTIVE")
        if symbols:
            upper_syms = [s.strip().upper() for s in symbols]
            asset_query = asset_query.filter(Asset.symbol.in_(upper_syms))
        if asset_ids:
            asset_query = asset_query.filter(Asset.id.in_(asset_ids))

        assets = asset_query.all()
        if not assets:
            return {}

        target_aids = [a.id for a in assets]
        sym_by_id = {a.id: a.symbol for a in assets}

        # Grouped subquery to get max observation_date per asset_id <= as_of
        subq = (
            session.query(
                Price.asset_id,
                func.max(Price.observation_date).label("max_date")
            )
            .filter(
                Price.asset_id.in_(target_aids),
                Price.status == "VALID",
                Price.observation_date <= as_of,
            )
            .group_by(Price.asset_id)
            .subquery()
        )

        price_rows = (
            session.query(Price)
            .join(
                subq,
                (Price.asset_id == subq.c.asset_id) & (Price.observation_date == subq.c.max_date)
            )
            .filter(Price.status == "VALID")
            .all()
        )

        price_by_aid = {pr.asset_id: pr for pr in price_rows}
        results: Dict[str, CanonicalPrice] = {}

        for asset in assets:
            pr = price_by_aid.get(asset.id)
            results[asset.symbol] = cls._build_canonical_price(asset.symbol, asset.id, pr, as_of, price_basis)

        return results

    @classmethod
    def get_latest_price_value(
        cls,
        session: Session,
        symbol: str,
        as_of: Optional[date] = None,
        price_basis: Literal["ADJUSTED", "RAW"] = "ADJUSTED",
    ) -> Optional[float]:
        """Convenience method returning float or None."""
        cp = cls.resolve_price(session, symbol, as_of, price_basis)
        return cp.price

    @staticmethod
    def _build_canonical_price(
        symbol: str,
        asset_id: int,
        p: Optional[Price],
        as_of: date,
        price_basis: Literal["ADJUSTED", "RAW"],
    ) -> CanonicalPrice:
        if not p:
            return CanonicalPrice(
                symbol=symbol,
                asset_id=asset_id,
                observation_date=None,
                price=None,
                adjusted_close=None,
                raw_close=None,
                adjustment_factor=None,
                volume=None,
                status="NOT_VERIFIED",
                source=None,
                is_stale=False,
                data_origin="NO_PRICE_RECORD",
            )

        raw = float(p.raw_close) if p.raw_close is not None else None
        adj = float(p.adjusted_close) if p.adjusted_close is not None else None

        if price_basis == "RAW":
            effective_price = raw if raw is not None else adj
        else:
            effective_price = adj if adj is not None else raw

        days_diff = (as_of - p.observation_date).days if p.observation_date else 999
        is_stale = days_diff > 7

        if effective_price is None:
            status = "NOT_VERIFIED"
        elif is_stale:
            status = "STALE"
        elif raw is None or adj is None:
            status = "PARTIAL"
        else:
            status = "AVAILABLE"

        return CanonicalPrice(
            symbol=symbol,
            asset_id=asset_id,
            observation_date=p.observation_date,
            price=effective_price,
            adjusted_close=adj,
            raw_close=raw,
            adjustment_factor=float(p.adjustment_factor) if p.adjustment_factor is not None else None,
            volume=float(p.volume) if p.volume is not None else None,
            status=status,
            source=p.source,
            is_stale=is_stale,
            data_origin="CANONICAL_DATABASE_PRICE",
        )

