"""
InvestIntel Dependency and Invalidation Model (Phase 7).

Ensures that whenever an upstream primary input changes (e.g. statement restatement,
adjusted price update, corporate action, share count correction), all downstream
derived calculations (Snapshot -> TTM -> Valuation Multiples -> Decision Context -> AI Evidence)
are deterministically identified, invalidated or marked STALE, and prevented from silent publication.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Set, Optional, Any
from pydantic import BaseModel, Field


class DependencyNodeType(str, Enum):
    # Primary Inputs
    RAW_PRICE = "RAW_PRICE"
    ADJUSTED_PRICE = "ADJUSTED_PRICE"
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    SHARE_COUNT = "SHARE_COUNT"
    CORPORATE_ACTION = "CORPORATE_ACTION"

    # Tier 1 Derived
    FINANCIAL_SNAPSHOT = "FINANCIAL_SNAPSHOT"
    TTM_INCOME = "TTM_INCOME"
    BOOK_VALUE = "BOOK_VALUE"

    # Tier 2 Derived
    EPS_TTM = "EPS_TTM"
    BVPS = "BVPS"
    ROE = "ROE"
    ROA = "ROA"

    # Tier 3 Derived
    PE_RATIO = "PE_RATIO"
    PB_RATIO = "PB_RATIO"
    MARKET_CAP = "MARKET_CAP"

    # Tier 4 Decision & AI Context
    DECISION_CONTEXT = "DECISION_CONTEXT"
    AI_EVIDENCE = "AI_EVIDENCE"
    AI_ANALYSIS = "AI_ANALYSIS"


class NodeState(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"
    PENDING_RECOMPUTE = "PENDING_RECOMPUTE"


class InvalidationEvent(BaseModel):
    symbol: str
    trigger_input: DependencyNodeType
    trigger_reason: str
    invalidated_nodes: List[DependencyNodeType]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recomputed_nodes: List[DependencyNodeType] = Field(default_factory=list)


# Static Dependency Graph defining what each derived node depends on
UPSTREAM_DEPENDENCIES: Dict[DependencyNodeType, Set[DependencyNodeType]] = {
    DependencyNodeType.ADJUSTED_PRICE: {
        DependencyNodeType.RAW_PRICE,
        DependencyNodeType.CORPORATE_ACTION,
    },
    DependencyNodeType.SHARE_COUNT: {
        DependencyNodeType.CORPORATE_ACTION,
    },
    DependencyNodeType.FINANCIAL_SNAPSHOT: {
        DependencyNodeType.INCOME_STATEMENT,
        DependencyNodeType.BALANCE_SHEET,
        DependencyNodeType.SHARE_COUNT,
    },
    DependencyNodeType.TTM_INCOME: {
        DependencyNodeType.INCOME_STATEMENT,
    },
    DependencyNodeType.BOOK_VALUE: {
        DependencyNodeType.BALANCE_SHEET,
    },
    DependencyNodeType.EPS_TTM: {
        DependencyNodeType.TTM_INCOME,
        DependencyNodeType.SHARE_COUNT,
    },
    DependencyNodeType.BVPS: {
        DependencyNodeType.BOOK_VALUE,
        DependencyNodeType.SHARE_COUNT,
    },
    DependencyNodeType.ROE: {
        DependencyNodeType.TTM_INCOME,
        DependencyNodeType.BOOK_VALUE,
    },
    DependencyNodeType.ROA: {
        DependencyNodeType.TTM_INCOME,
        DependencyNodeType.BALANCE_SHEET,
    },
    DependencyNodeType.MARKET_CAP: {
        DependencyNodeType.ADJUSTED_PRICE,
        DependencyNodeType.SHARE_COUNT,
    },
    DependencyNodeType.PE_RATIO: {
        DependencyNodeType.ADJUSTED_PRICE,
        DependencyNodeType.EPS_TTM,
    },
    DependencyNodeType.PB_RATIO: {
        DependencyNodeType.ADJUSTED_PRICE,
        DependencyNodeType.BVPS,
    },
    DependencyNodeType.DECISION_CONTEXT: {
        DependencyNodeType.PE_RATIO,
        DependencyNodeType.PB_RATIO,
        DependencyNodeType.ROE,
        DependencyNodeType.MARKET_CAP,
    },
    DependencyNodeType.AI_EVIDENCE: {
        DependencyNodeType.PE_RATIO,
        DependencyNodeType.PB_RATIO,
        DependencyNodeType.EPS_TTM,
        DependencyNodeType.BVPS,
        DependencyNodeType.ROE,
    },
    DependencyNodeType.AI_ANALYSIS: {
        DependencyNodeType.AI_EVIDENCE,
        DependencyNodeType.DECISION_CONTEXT,
    },
}


class DataDependencyGraph:
    """
    Manages dependency relationships, invalidation propagation, and publication gates
    for financial data in InvestIntel.
    """

    def __init__(self):
        # Maps (symbol, node_type) -> NodeState
        self._states: Dict[tuple[str, DependencyNodeType], NodeState] = {}
        # Invalidation history for reproducibility and audit
        self._history: List[InvalidationEvent] = []

    def set_node_state(self, symbol: str, node: DependencyNodeType, state: NodeState) -> None:
        self._states[(symbol.upper(), node)] = state

    def get_node_state(self, symbol: str, node: DependencyNodeType) -> NodeState:
        return self._states.get((symbol.upper(), node), NodeState.VALID)

    def find_all_dependents(self, trigger: DependencyNodeType) -> List[DependencyNodeType]:
        """
        Traverses downstream dependencies using breadth-first search to find all nodes
        that transitively depend on the trigger input.
        """
        downstream: List[DependencyNodeType] = []
        queue = [trigger]
        visited = {trigger}

        while queue:
            curr = queue.pop(0)
            for node, upstreams in UPSTREAM_DEPENDENCIES.items():
                if curr in upstreams and node not in visited:
                    visited.add(node)
                    downstream.append(node)
                    queue.append(node)

        return downstream

    def invalidate_dependents(
        self,
        symbol: str,
        trigger_input: DependencyNodeType,
        reason: str,
    ) -> InvalidationEvent:
        """
        Marks all downstream dependents as INVALIDATED when an upstream input changes.
        """
        sym = symbol.upper()
        affected = self.find_all_dependents(trigger_input)
        
        for node in affected:
            self.set_node_state(sym, node, NodeState.INVALIDATED)

        event = InvalidationEvent(
            symbol=sym,
            trigger_input=trigger_input,
            trigger_reason=reason,
            invalidated_nodes=affected,
        )
        self._history.append(event)
        return event

    def is_publishable(self, symbol: str, node: DependencyNodeType) -> tuple[bool, Optional[str]]:
        """
        Evaluates whether a derived node can be safely published.
        Blocks publication if any upstream dependency is INVALIDATED or STALE.
        """
        sym = symbol.upper()
        curr_state = self.get_node_state(sym, node)
        if curr_state != NodeState.VALID:
            return False, f"Node {node.value} state is {curr_state.value}"

        upstreams = UPSTREAM_DEPENDENCIES.get(node, set())
        for up in upstreams:
            up_state = self.get_node_state(sym, up)
            if up_state != NodeState.VALID:
                return False, f"Upstream dependency {up.value} is {up_state.value}"

        return True, None

    def get_invalidation_history(self, symbol: Optional[str] = None) -> List[InvalidationEvent]:
        if symbol is None:
            return list(self._history)
        sym = symbol.upper()
        return [e for e in self._history if e.symbol == sym]


# Global singleton instance for platform-wide invalidation tracking
invalidation_graph = DataDependencyGraph()
