from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from engine.parser import parse_netlist
from engine.units_detect import detect_diode_connected, detect_current_mirrors, detect_diff_pairs
from engine.dependency import build_unit_dependency_graph, reachable_units
from engine.ranking import compute_scores, rank_weak_points


def analyze_netlist(netlist_path: str) -> Dict[str, Any]:
    path = Path(netlist_path)

    mos, pas = parse_netlist(path)

    units = []
    units += detect_diode_connected(mos)
    units += detect_current_mirrors(mos)
    units += detect_diff_pairs(mos)

    deps = build_unit_dependency_graph(units, mos)

    compute_scores(units, mos, deps)
    ranked = rank_weak_points(units)

    unit_list = []
    for u in ranked:
        reach = sorted(list(reachable_units(deps, u.id)))
        unit_list.append({
            "id": u.id,
            "type": u.type,
            "risk": round(u.risk, 3),
            "likelihood": round(u.likelihood, 3),
            "impact": round(u.impact, 3),
            "confidence": round(u.confidence, 3),
            "members": u.members,
            "why_detected": u.why_detected,
            "top_checks": sorted(u.checks, key=lambda x: x["severity"] * x["weight"], reverse=True)[:3],
            "explanation": u.explanation,
            "blast_radius": reach,
        })

    return {
        "netlist": str(path),
        "mos_count": len(mos),
        "passive_count": len(pas),
        "units": unit_list,
    }
