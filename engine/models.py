from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


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
    params: Dict[str, str] = field(default_factory=dict)
    device_type: str = "unknown"  # "nmos", "pmos", or "unknown"
    w: Optional[float] = None
    l: Optional[float] = None
    m: float = 1.0
    nf: float = 1.0
    subckt: str = "TOP"
    line_no: int = 0
    raw: str = ""


@dataclass(frozen=True)
class Passive:
    name: str
    n1: str
    n2: str
    value: str
    kind: str  # "R" or "C"
    params: Dict[str, str] = field(default_factory=dict)
    numeric_value: Optional[float] = None
    subckt: str = "TOP"
    line_no: int = 0
    raw: str = ""


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
