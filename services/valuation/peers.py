# -*- coding: utf-8 -*-
"""
Peer Comparison Engine — Phase 4C.
Provides institutional cross-sectional peer valuation & operational comparisons:
- Dynamic peer group resolution (canonical PeerGroup table + sector clustering)
- Multiples calculation: P/E, P/B, EV/EBITDA, ROE, Margins, Debt/Equity, Market Cap
- Deterministic calculation of peer medians & distributions
- Discount / premium analysis against industry peer benchmarks
- Fail-closed handling for incomplete peer data
"""
from datetime import date
from typing import Any, Dict, List, Optional
import statistics
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, Price, PeerGroup
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder


class PeerMetricRow(BaseModel):
    symbol: str
    name: str
    sector: str
    is_target: bool = False
    current_price: Optional[float] = None
    market_cap_billion_vnd: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    de_ratio: Optional[float] = None
    revenue_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None


class PeerComparisonResult(BaseModel):
    target_symbol: str
    peer_group_id: str
    peer_group_name: str
    as_of_date: date
    status: str
    peers_evaluated: int
    target_metrics: PeerMetricRow
    peer_table: List[PeerMetricRow]
    peer_median_pe: Optional[float] = None
    peer_mean_pe: Optional[float] = None
    peer_median_pb: Optional[float] = None
    peer_mean_pb: Optional[float] = None
    peer_median_roe: Optional[float] = None
    pe_discount_premium_pct: Optional[float] = None
    pb_discount_premium_pct: Optional[float] = None
    valuation_summary: str


class PeerComparisonEngine:
    """Computes cross-sectional peer metrics and valuation medians."""

    SECTOR_PEER_FALLBACKS = {
        "TECHNOLOGY": ["FPT", "CMG", "ELC"],
        "BANK": ["VCB", "MBB", "TCB", "ACB", "CTG", "BID"],
        "BANKING": ["VCB", "MBB", "TCB", "ACB", "CTG", "BID"],
        "RETAIL": ["MWG", "FRT", "DGW", "PNJ"],
        "MATERIALS": ["HPG", "HSG", "NKG", "BMP"],
        "MANUFACTURING": ["BMP", "HPG", "HSG", "GVR"],
        "ENERGY": ["PLX", "BSR", "GAS", "PVD"],
        "OIL_GAS": ["PLX", "BSR", "GAS", "PVD"],
        "UTILITIES": ["REE", "POW", "NT2", "BWE"],
        "UTILITY": ["REE", "POW", "NT2", "BWE"],
        "CONSUMER": ["VNM", "MSN", "SAB", "MCH"],
        "CONSUMER_GOODS": ["VNM", "MSN", "SAB", "MCH"],
        "REAL_ESTATE": ["VHM", "VIC", "VRE"],
        "CONGLOMERATE": ["VIC", "VHM", "MSN"],
        "SECURITIES": ["SSI", "VND", "HCM", "VCI"],
        "FINANCIALS": ["SSI", "VND", "HCM", "VCI"],
        "INDUSTRIAL": ["CII", "CTD", "CTR", "GEE", "GEX", "HHV", "PC1", "VCG"],
        "TRANSPORTATION": ["GMD", "HVN", "PVT", "VJC", "VSC", "VTP"],
    }

    def __init__(self, session: Session):
        self.session = session

    def resolve_peer_symbols(self, symbol: str, sector: Optional[str] = None) -> tuple[str, str, list[str]]:
        sym = symbol.upper()
        # 1. Check database PeerGroup
        try:
            groups = self.session.query(PeerGroup).all()
            for g in groups:
                if g.members and sym in g.members:
                    return g.peer_group_id, g.name, [m for m in g.members if m]
        except Exception:
            pass

        # 2. Check sector clustering with normalization
        from services.fundamentals.sector_models import get_sector_for_symbol, normalize_sector_name
        sec_key = get_sector_for_symbol(sym, sector)
        if sec_key in ("CONSUMER_GOODS",):
            sec_key = "CONSUMER"
        elif sec_key in ("OIL_AND_GAS",):
            sec_key = "OIL_GAS"
        elif sec_key in ("UTILITIES",):
            sec_key = "UTILITY"

        if sec_key in self.SECTOR_PEER_FALLBACKS:
            peer_list = list(self.SECTOR_PEER_FALLBACKS[sec_key])
            if sym not in peer_list:
                peer_list.insert(0, sym)
            return f"{sec_key}_PEERS", f"Vietnam {sec_key.title()} Industry Peers", peer_list

        # 3. Default fallback
        return "GENERAL_PEERS", "Vietnam Market Peers", [sym]

    def _get_stock_row(self, sym: str, as_of: date, is_target: bool = False) -> Optional[PeerMetricRow]:
        asset = self.session.query(Asset).filter(Asset.symbol == sym).first()
        name = asset.name if asset else f"{sym} Corporation"
        from services.fundamentals.sector_models import get_sector_for_symbol
        sec = get_sector_for_symbol(sym, asset.sector if asset else None)

        # Price lookup
        price = None
        if asset:
            from services.market.canonical_price import CanonicalPriceResolver
            price = CanonicalPriceResolver.get_latest_price_value(self.session, sym, as_of)

        # Fundamentals lookup
        repo = FinancialRepository(self.session)
        dataset = repo.get_financial_dataset(sym, as_of_date=as_of)
        if not dataset:
            return PeerMetricRow(
                symbol=sym,
                name=name,
                sector=sec,
                is_target=is_target,
                current_price=price,
            )

        builder = FundamentalSnapshotBuilder(sym, sec)
        snap = builder.build_snapshot(
            income_quarters=dataset["income_quarters"],
            income_annual=dataset["income_annual"],
            balance_annual=dataset["balance_annual"],
            cashflow_annual=dataset["cashflow_annual"],
            shares_outstanding=dataset.get("shares_outstanding"),
            as_of_date=as_of,
        )

        eps = snap.get("eps_ttm") or snap.get("eps_basic")
        bvps = snap.get("bvps")
        shares = dataset.get("shares_outstanding")
        mcap = round((price * shares) / 1e9, 2) if (price and shares) else None

        pe_val = round(price / eps, 2) if (price and eps and eps > 0) else None
        pb_val = round(price / bvps, 2) if (price and bvps and bvps > 0) else None

        gm_r = snap.get("profitability", {}).get("gross_margin", {})
        gm = gm_r.get("value") if isinstance(gm_r, dict) else None

        nm_r = snap.get("profitability", {}).get("net_margin", {})
        nm = nm_r.get("value") if isinstance(nm_r, dict) else None

        roe_r = snap.get("profitability", {}).get("roe", {})
        roe = roe_r.get("value") if isinstance(roe_r, dict) else None

        de_r = snap.get("balance_sheet", {}).get("de_ratio", {})
        de = de_r.get("value") if isinstance(de_r, dict) else None

        return PeerMetricRow(
            symbol=sym,
            name=name,
            sector=sec,
            is_target=is_target,
            current_price=price,
            market_cap_billion_vnd=mcap,
            pe=pe_val,
            pb=pb_val,
            roe=round(roe, 2) if roe is not None else None,
            gross_margin=round(gm, 2) if gm is not None else None,
            net_margin=round(nm, 2) if nm is not None else None,
            de_ratio=round(de, 4) if de is not None else None,
            revenue_ttm=snap.get("revenue_ttm"),
            net_income_ttm=snap.get("net_income_ttm"),
        )

    def compare_peers(self, symbol: str, as_of: Optional[date] = None) -> PeerComparisonResult:
        as_of = as_of or date.today()
        sym = symbol.upper()

        asset = self.session.query(Asset).filter(Asset.symbol == sym).first()
        sector = asset.sector if (asset and asset.sector) else None
        if not sector or sector.upper() == "GENERAL":
            from services.fundamentals.sector_models import get_sector_for_symbol
            sector = get_sector_for_symbol(sym)
        if not sector:
            repo = FinancialRepository(self.session)
            ds = repo.get_financial_dataset(sym, as_of_date=as_of)
            if ds and ds.get("sector"):
                sector = ds["sector"]

        group_id, group_name, peer_symbols = self.resolve_peer_symbols(sym, sector)

        # Build metric row for target
        target_row = self._get_stock_row(sym, as_of, is_target=True)

        # Build metric rows for all peers
        peer_table: list[PeerMetricRow] = []
        for p_sym in peer_symbols:
            if p_sym == sym:
                peer_table.append(target_row)
            else:
                row = self._get_stock_row(p_sym, as_of, is_target=False)
                if row:
                    peer_table.append(row)

        # Filter strictly peer candidates (excluding target) for statistics
        other_peers = [r for r in peer_table if not r.is_target]

        valid_pes = [r.pe for r in other_peers if r.pe is not None and r.pe > 0]
        valid_pbs = [r.pb for r in other_peers if r.pb is not None and r.pb > 0]
        valid_roes = [r.roe for r in other_peers if r.roe is not None]

        med_pe = round(statistics.median(valid_pes), 2) if valid_pes else None
        mean_pe = round(statistics.mean(valid_pes), 2) if valid_pes else None

        med_pb = round(statistics.median(valid_pbs), 2) if valid_pbs else None
        mean_pb = round(statistics.mean(valid_pbs), 2) if valid_pbs else None

        med_roe = round(statistics.median(valid_roes), 2) if valid_roes else None

        # Discount / Premium calculations
        pe_diff = None
        if target_row.pe and med_pe and med_pe > 0:
            pe_diff = round(((target_row.pe - med_pe) / med_pe) * 100, 1)

        pb_diff = None
        if target_row.pb and med_pb and med_pb > 0:
            pb_diff = round(((target_row.pb - med_pb) / med_pb) * 100, 1)

        # Valuation narrative summary
        if pe_diff is not None:
            if pe_diff < -10:
                summary = f"{sym} đang giao dịch ở mức định giá chiết khấu P/E {abs(pe_diff):.1f}% so với trung vị ngành ({med_pe:.1f}x so với {target_row.pe:.1f}x)."
            elif pe_diff > 10:
                summary = f"{sym} đang giao dịch ở mức cao hơn {pe_diff:.1f}% P/E trung vị ngành ({target_row.pe:.1f}x so với {med_pe:.1f}x), phản ánh kỳ vọng chất lượng hoặc tỷ suất sinh lời vượt trội."
            else:
                summary = f"{sym} đang giao dịch tương đương trung vị P/E ngành (chênh lệch {pe_diff:+.1f}%)."
        else:
            summary = f"Đã thu thập dữ liệu so sánh định giá cho {len(peer_table)} doanh nghiệp trong nhóm ngành {group_name}."

        return PeerComparisonResult(
            target_symbol=sym,
            peer_group_id=group_id,
            peer_group_name=group_name,
            as_of_date=as_of,
            status="AVAILABLE" if len(peer_table) >= 2 else "PARTIAL",
            peers_evaluated=len(peer_table),
            target_metrics=target_row,
            peer_table=peer_table,
            peer_median_pe=med_pe,
            peer_mean_pe=mean_pe,
            peer_median_pb=med_pb,
            peer_mean_pb=mean_pb,
            peer_median_roe=med_roe,
            pe_discount_premium_pct=pe_diff,
            pb_discount_premium_pct=pb_diff,
            valuation_summary=summary,
        )
