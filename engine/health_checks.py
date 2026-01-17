from __future__ import annotations

from typing import Dict, List, Set

from .models import Mosfet, Unit
from .dependency import spof_bonus
from .utils import clip, looks_like_supply, is_ground, label_severity


def run_health_checks(u: Unit, mos: Dict[str, Mosfet], deps: Dict[str, Set[str]]) -> List[dict]:
    checks: List[dict] = []

    # Common: fanout/loading
    fanout = len(deps.get(u.id, set()))
    fanout_sev = clip(fanout / 5.0)
    checks.append({
        "name": "LoadFanout",
        "severity": fanout_sev,
        "weight": 0.20,
        "observed": f"fanout={fanout}",
        "expected": "lower is safer (<=2 ideal)",
        "severity_label": label_severity(fanout_sev),
    })

    if u.type == "CurrentMirror":
        members = [mos[m] for m in u.members if m in mos]
        out_drains = [m.d for m in members]
        internal_outputs = sum(1 for d in out_drains if not looks_like_supply(d) and not is_ground(d))
        headroom_sev = clip(internal_outputs / 2.0)
        checks.append({
            "name": "HeadroomProxy",
            "severity": headroom_sev,
            "weight": 0.35,
            "observed": f"internal_output_drains={internal_outputs}/2 ({out_drains})",
            "expected": "internal outputs often imply tighter headroom",
            "severity_label": label_severity(headroom_sev),
        })

        spof = spof_bonus(u.id, deps)
        spof_sev = clip(spof / 0.20)
        checks.append({
            "name": "SinglePointFailure",
            "severity": spof_sev,
            "weight": 0.15,
            "observed": f"spof_bonus={spof:.2f} (from fanout)",
            "expected": "lower is safer",
            "severity_label": label_severity(spof_sev),
        })

        sens_sev = clip(fanout / 6.0)
        checks.append({
            "name": "BiasSensitivityProxy",
            "severity": sens_sev,
            "weight": 0.20,
            "observed": f"bias_gate_used_by_units={fanout}",
            "expected": "bias nets should be stable/isolated",
            "severity_label": label_severity(sens_sev),
        })

    elif u.type == "DiffPair":
        a, b = [mos[m] for m in u.members if m in mos]
        mismatch_sev = 0.0
        if a.b != b.b:
            mismatch_sev += 0.4
        if looks_like_supply(a.d) or looks_like_supply(b.d):
            mismatch_sev += 0.3
        mismatch_sev = clip(mismatch_sev)

        checks.append({
            "name": "SymmetryProxy",
            "severity": mismatch_sev,
            "weight": 0.15,
            "observed": f"bulk_match={a.b==b.b}, drains=({a.d},{b.d})",
            "expected": "diff pairs rely on symmetry/matching",
            "severity_label": label_severity(mismatch_sev),
        })

        tail = a.s
        tail_sev = 0.9 if is_ground(tail) else 0.0
        checks.append({
            "name": "TailNodeProxy",
            "severity": tail_sev,
            "weight": 0.35,
            "observed": f"tail_node={tail}",
            "expected": "tail node usually not ground",
            "severity_label": label_severity(tail_sev),
        })

        checks.append({
            "name": "BiasDependencyProxy",
            "severity": 0.2,
            "weight": 0.20,
            "observed": "heuristic",
            "expected": "diff pairs depend on stable biasing",
            "severity_label": "low",
        })

    elif u.type == "DiodeConnected":
        m = mos[u.members[0]]
        sev = 0.5 if (not looks_like_supply(m.g) and not is_ground(m.g)) else 0.2
        checks.append({
            "name": "DiodeSensitivityProxy",
            "severity": sev,
            "weight": 0.25,
            "observed": f"diode_node={m.g}",
            "expected": "reference nodes can be sensitive",
            "severity_label": label_severity(sev),
        })

    else:
        checks.append({
            "name": "GenericProxy",
            "severity": 0.2,
            "weight": 0.20,
            "observed": "n/a",
            "expected": "n/a",
            "severity_label": "low",
        })

    return checks
