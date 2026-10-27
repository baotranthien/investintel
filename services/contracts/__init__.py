"""
InvestIntel Data Contracts Layer.

Provides unified, enforceable contracts for:
- Price semantics and geometry
- Share count purpose-specific resolution
- Quarterly statement continuity
- Valuation metrics and outlier handling
- Dependency graph and downstream invalidation
"""

from .semantic_types import (
    PriceSemantics,
    ShareType,
    StatementPeriodType,
    VerificationLevel,
    ConsolidationBasis,
    PriceContract,
    ShareResolutionContract,
    StatementPeriodContract,
    MetricCalculationContract,
)

from .validators import (
    validate_price_payload,
    resolve_shares_by_purpose,
    validate_quarterly_continuity,
    validate_valuation_ratio,
)

from .invalidation import (
    DependencyNodeType,
    NodeState,
    InvalidationEvent,
    DataDependencyGraph,
    invalidation_graph,
)

__all__ = [
    "PriceSemantics",
    "ShareType",
    "StatementPeriodType",
    "VerificationLevel",
    "ConsolidationBasis",
    "PriceContract",
    "ShareResolutionContract",
    "StatementPeriodContract",
    "MetricCalculationContract",
    "validate_price_payload",
    "resolve_shares_by_purpose",
    "validate_quarterly_continuity",
    "validate_valuation_ratio",
    "DependencyNodeType",
    "NodeState",
    "InvalidationEvent",
    "DataDependencyGraph",
    "invalidation_graph",
]
