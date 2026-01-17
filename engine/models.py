from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set


@dataclass(frozen=True)
class Mosfet:
    """
    SPICE MOS line assumed:
      Mname drain gate source bulk model
    """
    name: str
    d: str
    g: str
    s: str
    b: str
    model: str


@dataclass(frozen=True)
class Passive:
    name: str
    n1: str
    n2: str
    value: str
    kind: str  # "R" or "C"


@dataclass
class Unit:
    """
    A detected functional unit (diff pair, mirror, etc.)
    """
    id: str
    type: str
    members: List[str]
    nets: Set[str] = field(default_factory=set)

    # Confidence components
    detect_conf: float = 0.85
    check_conf: float = 0.80
    impact_conf: float = 0.75

    # Filled later
    likelihood: float = 0.0
    impact: float = 0.0
    confidence: float = 0.0
    risk: float = 0.0

    why_detected: List[str] = field(default_factory=list)
    checks: List[dict] = field(default_factory=list)
    explanation: str = ""
