from __future__ import annotations

from typing import Dict, List, Set

from .models import Mosfet, Unit
from .dependency import spof_bonus
from .utils import clip, equivalent_width, looks_like_supply, is_ground, label_severity, rel_delta


def _members(u: Unit, mos: Dict[str, Mosfet]) -> List[Mosfet]:
    return [mos[m] for m in u.members if m in mos]


def _sizing_mismatch(a: Mosfet, b: Mosfet) -> float | None:
    w_delta = rel_delta(equivalent_width(a.w, a.m, a.nf), equivalent_width(b.w, b.m, b.nf))
    l_delta = rel_delta(a.l, b.l)
    values = [v for v in (w_delta, l_delta) if v is not None]
    if not values:
        return None
    return max(values)


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
        members = _members(u, mos)
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

        if len(members) >= 2:
            mismatch = _sizing_mismatch(members[0], members[1])
            if mismatch is None:
                sev = 0.35
                observed = "W/L or multiplicity missing"
            else:
                sev = clip(mismatch / 0.15)
                observed = f"relative_sizing_delta={mismatch:.3g}"
            checks.append({
                "name": "MirrorSizingConsistency",
                "severity": sev,
                "weight": 0.30,
                "observed": observed,
                "expected": "matched mirrors should have intentional, explainable ratios",
                "severity_label": label_severity(sev),
            })

            bulk_match = all(m.b == members[0].b for m in members)
            sev = 0.0 if bulk_match else 0.65
            checks.append({
                "name": "MirrorBodyTie",
                "severity": sev,
                "weight": 0.15,
                "observed": f"bulk_nets={[m.b for m in members]}",
                "expected": "mirror devices normally share compatible body ties",
                "severity_label": label_severity(sev),
            })

    elif u.type == "DiffPair":
        members = _members(u, mos)
        if len(members) < 2:
            return checks
        a, b = members[:2]
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

        mismatch = _sizing_mismatch(a, b)
        if mismatch is None:
            sev = 0.35
            observed = "W/L or multiplicity missing"
        else:
            sev = clip(mismatch / 0.05)
            observed = f"relative_sizing_delta={mismatch:.3g}"
        checks.append({
            "name": "InputPairSizingMatch",
            "severity": sev,
            "weight": 0.30,
            "observed": observed,
            "expected": "input pair devices should match unless intentionally weighted",
            "severity_label": label_severity(sev),
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

    elif u.type == "TailCurrentSource":
        members = _members(u, mos)
        m = members[0] if members else None
        gate_known = bool(m and not is_ground(m.g) and not looks_like_supply(m.g))
        sev = 0.2 if gate_known else 0.75
        checks.append({
            "name": "TailBiasControl",
            "severity": sev,
            "weight": 0.35,
            "observed": f"gate={m.g if m else 'unknown'}",
            "expected": "tail current source gate should be driven by a defined bias",
            "severity_label": label_severity(sev),
        })
        checks.append({
            "name": "TailCommonModeSensitivity",
            "severity": 0.45,
            "weight": 0.20,
            "observed": "tail source controls differential pair operating point",
            "expected": "verify compliance across input common-mode range",
            "severity_label": "low",
        })

    elif u.type == "CascodeStack":
        members = _members(u, mos)
        known_biases = sum(1 for m in members if not is_ground(m.g) and not looks_like_supply(m.g))
        sev = 0.25 if known_biases == len(members) else 0.70
        checks.append({
            "name": "CascodeBiasPresence",
            "severity": sev,
            "weight": 0.30,
            "observed": f"gate_nets={[m.g for m in members]}",
            "expected": "each stacked device needs a valid bias/control gate",
            "severity_label": label_severity(sev),
        })
        checks.append({
            "name": "StackHeadroomRisk",
            "severity": 0.65,
            "weight": 0.35,
            "observed": f"stack_devices={len(members)}",
            "expected": "stacked devices consume voltage headroom",
            "severity_label": "medium",
        })

    elif u.type == "BiasNetwork":
        fanout_sev = clip(fanout / 4.0)
        checks.append({
            "name": "BiasFanout",
            "severity": fanout_sev,
            "weight": 0.35,
            "observed": f"dependent_units={fanout}",
            "expected": "high fanout bias references deserve isolation or buffering",
            "severity_label": label_severity(fanout_sev),
        })
        diode_count = sum(1 for m in _members(u, mos) if m.g == m.d)
        sev = 0.2 if diode_count else 0.8
        checks.append({
            "name": "ReferenceGeneration",
            "severity": sev,
            "weight": 0.25,
            "observed": f"diode_connected_devices={diode_count}",
            "expected": "bias network should have an identifiable reference generator",
            "severity_label": label_severity(sev),
        })
        checks.append({
            "name": "StartupReview",
            "severity": 0.55,
            "weight": 0.20,
            "observed": "startup path not proven from static netlist",
            "expected": "self-biased networks usually need startup verification",
            "severity_label": "medium",
        })

    elif u.type == "ActiveLoadPair":
        members = _members(u, mos)
        if len(members) >= 2:
            mismatch = _sizing_mismatch(members[0], members[1])
            sev = 0.35 if mismatch is None else clip(mismatch / 0.10)
            checks.append({
                "name": "LoadPairSymmetry",
                "severity": sev,
                "weight": 0.30,
                "observed": "W/L missing" if mismatch is None else f"relative_sizing_delta={mismatch:.3g}",
                "expected": "active load pair should be symmetric unless intentionally skewed",
                "severity_label": label_severity(sev),
            })
        checks.append({
            "name": "OutputSwingReview",
            "severity": 0.45,
            "weight": 0.20,
            "observed": "active load touches output nodes",
            "expected": "verify output swing and saturation margins",
            "severity_label": "low",
        })

    elif u.type == "SourceFollower":
        members = _members(u, mos)
        m = members[0] if members else None
        body_ok = bool(m and (m.b == m.s or looks_like_supply(m.b) or is_ground(m.b)))
        sev = 0.2 if body_ok else 0.60
        checks.append({
            "name": "FollowerBodyEffect",
            "severity": sev,
            "weight": 0.25,
            "observed": f"source={m.s if m else 'unknown'}, bulk={m.b if m else 'unknown'}",
            "expected": "body effect can shift follower level and degrade accuracy",
            "severity_label": label_severity(sev),
        })
        checks.append({
            "name": "FollowerHeadroom",
            "severity": 0.45,
            "weight": 0.25,
            "observed": "source follower requires Vgs/Vov headroom",
            "expected": "verify rail-to-output margin",
            "severity_label": "low",
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
