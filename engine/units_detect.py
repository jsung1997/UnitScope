from __future__ import annotations

from typing import Dict, List

from .models import Mosfet, Unit
from .utils import clip, looks_like_supply, is_ground


def detect_diode_connected(mos: Dict[str, Mosfet]) -> List[Unit]:
    units: List[Unit] = []
    idx = 1
    for m in mos.values():
        if m.g == m.d:
            u = Unit(
                id=f"U_DIODE_{idx}",
                type="DiodeConnected",
                members=[m.name],
                nets={m.g, m.s, m.b},
                detect_conf=0.95,
                check_conf=0.80,
                impact_conf=0.60,
            )
            u.why_detected = [f"{m.name} is diode-connected because gate == drain ({m.g})."]
            units.append(u)
            idx += 1
    return units


def detect_current_mirrors(mos: Dict[str, Mosfet]) -> List[Unit]:
    """
    Simple 2-transistor mirror:
      - Mx diode-connected (g == d)
      - My shares gate and source with Mx
      - same model
    """
    units: List[Unit] = []
    names = sorted(mos.keys())
    diode = {n for n, m in mos.items() if m.g == m.d}
    idx = 1

    for dname in sorted(diode):
        md = mos[dname]
        for oname in names:
            if oname == dname:
                continue
            mo = mos[oname]

            if md.model != mo.model:
                continue
            if md.g != mo.g:
                continue
            if md.s != mo.s:
                continue

            detect_conf = 0.90
            if looks_like_supply(md.d) or looks_like_supply(mo.d):
                detect_conf -= 0.10

            u = Unit(
                id=f"U_MIRROR_{idx}",
                type="CurrentMirror",
                members=[md.name, mo.name],
                nets={md.g, md.s, md.b, md.d, mo.d},
                detect_conf=clip(detect_conf, 0.5, 0.95),
                check_conf=0.75,
                impact_conf=0.75,
            )
            u.why_detected = [
                f"{md.name} is diode-connected (G=D={md.g}).",
                f"{mo.name} shares gate with {md.name} (G={mo.g}).",
                f"{mo.name} shares source with {md.name} (S={mo.s}).",
                f"Both are same model type ({md.model}).",
            ]
            units.append(u)
            idx += 1

    return units


def detect_diff_pairs(mos: Dict[str, Mosfet]) -> List[Unit]:
    """
    Simple diff pair:
      - same model
      - shared source
      - different gates
      - different drains
    """
    units: List[Unit] = []
    names = sorted(mos.keys())
    idx = 1

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = mos[names[i]]
            b = mos[names[j]]

            if a.model != b.model:
                continue
            if a.s != b.s:
                continue
            if a.g == b.g:
                continue
            if a.d == b.d:
                continue

            conf = 0.75
            if a.b == b.b:
                conf += 0.10
            if not looks_like_supply(a.d) and not looks_like_supply(b.d):
                conf += 0.05
            conf = clip(conf, 0.5, 0.95)

            u = Unit(
                id=f"U_DIFF_{idx}",
                type="DiffPair",
                members=[a.name, b.name],
                nets={a.s, a.g, b.g, a.d, b.d, a.b, b.b},
                detect_conf=conf,
                check_conf=0.75,
                impact_conf=0.70,
            )
            u.why_detected = [
                f"{a.name} and {b.name} share source net ({a.s}).",
                f"Gates are different ({a.g} vs {b.g}).",
                f"Drains are different ({a.d} vs {b.d}).",
                f"Same model type ({a.model}).",
            ]
            units.append(u)
            idx += 1

    return units
