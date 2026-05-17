from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict

from engine.config import PdkConfig, load_pdk_config, set_active_pdk_config
from engine.parser import parse_netlist
from engine.units_detect import (
    detect_active_load_pairs,
    detect_bias_networks,
    detect_cascode_stacks,
    detect_current_mirrors,
    detect_diff_pairs,
    detect_diode_connected,
    detect_source_followers,
    detect_tail_current_sources,
)
from engine.dependency import build_unit_dependency_graph, reachable_units
from engine.ranking import compute_scores, rank_weak_points


def analyze_netlist(
    netlist_path: str,
    pdk_config: PdkConfig | None = None,
    pdk_config_path: str | None = None,
) -> Dict[str, Any]:
    path = Path(netlist_path)
    config = pdk_config or load_pdk_config(pdk_config_path)
    set_active_pdk_config(config)

    mos, pas = parse_netlist(path, config)

    units = []
    units += detect_diode_connected(mos)
    units += detect_current_mirrors(mos)
    units += detect_diff_pairs(mos)
    units += detect_tail_current_sources(mos)
    units += detect_cascode_stacks(mos)
    units += detect_bias_networks(mos)
    units += detect_active_load_pairs(mos)
    units += detect_source_followers(mos)

    deps = build_unit_dependency_graph(units, mos)

    compute_scores(units, mos, deps)
    ranked = rank_weak_points(units)

    unit_list = []
    for u in ranked:
        reach = sorted(list(reachable_units(deps, u.id)))
        member_details = []
        for name in u.members:
            if name not in mos:
                continue
            m = mos[name]
            member_details.append({
                "name": m.name,
                "subckt": m.subckt,
                "line_no": m.line_no,
                "pins": {"d": m.d, "g": m.g, "s": m.s, "b": m.b},
                "model": m.model,
                "device_type": m.device_type,
                "w": m.w,
                "l": m.l,
                "m": m.m,
                "nf": m.nf,
                "raw": m.raw,
            })
        unit_list.append({
            "id": u.id,
            "type": u.type,
            "risk": round(u.risk, 3),
            "likelihood": round(u.likelihood, 3),
            "impact": round(u.impact, 3),
            "confidence": round(u.confidence, 3),
            "members": u.members,
            "member_details": member_details,
            "why_detected": u.why_detected,
            "top_checks": sorted(u.checks, key=lambda x: x["severity"] * x["weight"], reverse=True)[:3],
            "checks": sorted(u.checks, key=lambda x: x["severity"] * x["weight"], reverse=True),
            "explanation": u.explanation,
            "blast_radius": reach,
        })

    return {
        "netlist": str(path),
        "pdk_config": config.to_dict(),
        "mos_count": len(mos),
        "passive_count": len(pas),
        "unit_type_counts": dict(Counter(u["type"] for u in unit_list)),
        "units": unit_list,
    }
