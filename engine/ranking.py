from __future__ import annotations

import math
from typing import Dict, List, Set

from .models import Mosfet, Unit
from .dependency import reachable_units, spof_bonus
from .health_checks import run_health_checks
from .utils import clip


def unit_type_impact(unit_type: str) -> float:
    table = {
        "BiasNetwork": 1.00,
        "CurrentMirror": 0.90,
        "TailCurrentSource": 0.85,
        "CascodeStack": 0.80,
        "DiffPair": 0.70,
        "ActiveLoadPair": 0.70,
        "SourceFollower": 0.55,
        "DiodeConnected": 0.50,
    }
    return table.get(unit_type, 0.50)


def unit_importance_for_spread(unit_type: str) -> float:
    table = {
        "BiasNetwork": 1.0,
        "CurrentMirror": 0.9,
        "TailCurrentSource": 0.85,
        "CascodeStack": 0.75,
        "DiffPair": 0.6,
        "ActiveLoadPair": 0.6,
        "SourceFollower": 0.45,
        "DiodeConnected": 0.4,
    }
    return table.get(unit_type, 0.5)


def compute_scores(units: List[Unit], mos: Dict[str, Mosfet], deps: Dict[str, Set[str]]) -> None:
    unit_by_id = {u.id: u for u in units}

    for u in units:
        checks = run_health_checks(u, mos, deps)
        u.checks = checks

        # Likelihood
        L = sum(c["severity"] * c["weight"] for c in checks)
        u.likelihood = clip(L)

        # Impact
        reach = reachable_units(deps, u.id)
        spread_weight = sum(unit_importance_for_spread(unit_by_id[v].type) for v in reach if v in unit_by_id)
        I_spread = 1 - math.exp(-0.4 * spread_weight)
        I_type = unit_type_impact(u.type)
        I_spof = spof_bonus(u.id, deps)

        u.impact = clip(0.5 * I_spread + 0.4 * I_type + 0.1 * (I_spof / 0.20 if I_spof > 0 else 0.0))

        # Confidence
        u.confidence = clip(0.5 * u.detect_conf + 0.3 * u.check_conf + 0.2 * u.impact_conf)

        # Risk
        u.risk = clip(u.likelihood * u.impact * u.confidence)

        # Explanation
        top = sorted(checks, key=lambda x: x["severity"] * x["weight"], reverse=True)[:3]
        reasons = "; ".join([f"{t['name']}={t['severity_label']} ({t['observed']})" for t in top])

        if len(reach) == 0:
            blast = "limited downstream dependencies"
        else:
            blast = f"affects {len(reach)} downstream unit(s): {', '.join(sorted(list(reach))[:5])}" + ("..." if len(reach) > 5 else "")

        u.explanation = f"Risk={u.risk:.2f} because {reasons}. Impact: {blast}."


def rank_weak_points(units: List[Unit]) -> List[Unit]:
    return sorted(units, key=lambda u: u.risk, reverse=True)
