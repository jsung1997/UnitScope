from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from .models import Mosfet, Passive


def parse_netlist(path: Path) -> Tuple[Dict[str, Mosfet], Dict[str, Passive]]:
    """
    Minimal SPICE-like parser.

    Supports:
      - MOSFET lines: Mname d g s b model
      - Resistor lines: Rname n1 n2 value
      - Capacitor lines: Cname n1 n2 value

    Ignores everything else.
    """
    mos: Dict[str, Mosfet] = {}
    pas: Dict[str, Passive] = {}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue

        if "*" in line:
            line = line.split("*", 1)[0].strip()

        toks = line.split()
        if not toks:
            continue

        head = toks[0]
        kind = head[0].upper()

        if kind == "M" and len(toks) >= 6:
            name = toks[0]
            d, g, s, b = toks[1], toks[2], toks[3], toks[4]
            model = toks[5]
            mos[name] = Mosfet(name=name, d=d, g=g, s=s, b=b, model=model)
            continue

        if kind in ("R", "C") and len(toks) >= 4:
            name = toks[0]
            n1, n2, value = toks[1], toks[2], toks[3]
            pas[name] = Passive(name=name, n1=n1, n2=n2, value=value, kind=kind)
            continue

    return mos, pas
