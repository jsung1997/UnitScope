from __future__ import annotations

from typing import Dict, List, Set

from .models import Mosfet, Unit


def build_unit_dependency_graph(units: List[Unit], mos: Dict[str, Mosfet]) -> Dict[str, Set[str]]:
    """
    Heuristic dependency graph:
    CurrentMirror biases another unit if the mirror's gate net appears as a gate
    on MOSFETs in that other unit.
    """
    unit_gate_nets: Dict[str, Set[str]] = {u.id: set() for u in units}
    for u in units:
        for dev in u.members:
            if dev in mos:
                unit_gate_nets[u.id].add(mos[dev].g)

    deps: Dict[str, Set[str]] = {u.id: set() for u in units}

    for u in units:
        if u.type != "CurrentMirror":
            continue

        mirror_gate_nets = set()
        for dev in u.members:
            if dev in mos:
                mirror_gate_nets.add(mos[dev].g)

        for v in units:
            if v.id == u.id:
                continue
            if unit_gate_nets[v.id].intersection(mirror_gate_nets):
                deps[u.id].add(v.id)

    return deps


def reachable_units(deps: Dict[str, Set[str]], start: str) -> Set[str]:
    seen: Set[str] = set()
    stack = [start]
    while stack:
        x = stack.pop()
        for y in deps.get(x, set()):
            if y not in seen:
                seen.add(y)
                stack.append(y)
    return seen


def spof_bonus(unit_id: str, deps: Dict[str, Set[str]]) -> float:
    out_deg = len(deps.get(unit_id, set()))
    if out_deg >= 4:
        return 0.20
    if out_deg == 3:
        return 0.15
    if out_deg == 2:
        return 0.10
    if out_deg == 1:
        return 0.05
    return 0.00
