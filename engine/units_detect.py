from __future__ import annotations

from collections import defaultdict
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


def detect_tail_current_sources(mos: Dict[str, Mosfet]) -> List[Unit]:
    shared_sources: Dict[str, List[Mosfet]] = defaultdict(list)
    for m in mos.values():
        shared_sources[m.s].append(m)

    units: List[Unit] = []
    idx = 1
    for tail_net, pair_devs in sorted(shared_sources.items()):
        same_model = defaultdict(list)
        for m in pair_devs:
            same_model[(m.model, m.device_type)].append(m)

        if not any(len(v) >= 2 for v in same_model.values()):
            continue

        for bias in mos.values():
            if bias.d != tail_net:
                continue
            source_is_rail = is_ground(bias.s) or looks_like_supply(bias.s)
            if not source_is_rail:
                continue
            u = Unit(
                id=f"U_TAIL_{idx}",
                type="TailCurrentSource",
                members=[bias.name],
                nets={bias.d, bias.g, bias.s, bias.b},
                detect_conf=0.82,
                check_conf=0.70,
                impact_conf=0.80,
            )
            u.why_detected = [
                f"{bias.name} drains into shared source/tail net {tail_net}.",
                f"{tail_net} is shared by multiple same-model input devices.",
                f"{bias.name} source is tied to rail-like net {bias.s}.",
            ]
            units.append(u)
            idx += 1
    return units


def detect_cascode_stacks(mos: Dict[str, Mosfet]) -> List[Unit]:
    units: List[Unit] = []
    idx = 1
    names = sorted(mos.keys())
    for lower_name in names:
        lower = mos[lower_name]
        for upper_name in names:
            if upper_name == lower_name:
                continue
            upper = mos[upper_name]
            if lower.model != upper.model:
                continue
            if lower.d != upper.s:
                continue
            if lower.g == upper.g:
                continue
            if lower.device_type != upper.device_type:
                continue

            u = Unit(
                id=f"U_CASCODE_{idx}",
                type="CascodeStack",
                members=[lower.name, upper.name],
                nets={lower.s, lower.d, lower.g, upper.d, upper.g, upper.b},
                detect_conf=0.78,
                check_conf=0.72,
                impact_conf=0.78,
            )
            u.why_detected = [
                f"{lower.name}.D connects to {upper.name}.S at {lower.d}.",
                f"Both devices share model/type ({lower.model}/{lower.device_type}).",
                f"Gate nets differ ({lower.g} vs {upper.g}), consistent with stack/cascode biasing.",
            ]
            units.append(u)
            idx += 1
    return units


def detect_bias_networks(mos: Dict[str, Mosfet]) -> List[Unit]:
    gate_users: Dict[str, List[Mosfet]] = defaultdict(list)
    diode_by_net: Dict[str, List[Mosfet]] = defaultdict(list)
    for m in mos.values():
        gate_users[m.g].append(m)
        if m.g == m.d:
            diode_by_net[m.g].append(m)

    units: List[Unit] = []
    idx = 1
    for net, diodes in sorted(diode_by_net.items()):
        users = gate_users.get(net, [])
        if len(users) < 2:
            continue
        members = sorted({m.name for m in diodes + users})
        u = Unit(
            id=f"U_BIAS_{idx}",
            type="BiasNetwork",
            members=members,
            nets={net} | {m.s for m in users} | {m.d for m in users},
            detect_conf=0.88,
            check_conf=0.72,
            impact_conf=0.88,
        )
        u.why_detected = [
            f"Bias/reference net {net} is generated by diode-connected device(s): {', '.join(m.name for m in diodes)}.",
            f"{len(users)} MOS gate(s) use {net}, so this net can control multiple units.",
        ]
        units.append(u)
        idx += 1
    return units


def detect_active_load_pairs(mos: Dict[str, Mosfet]) -> List[Unit]:
    units: List[Unit] = []
    names = sorted(mos.keys())
    idx = 1
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = mos[names[i]]
            b = mos[names[j]]
            if a.model != b.model or a.device_type != b.device_type:
                continue
            if a.s != b.s or not looks_like_supply(a.s):
                continue
            if a.d == b.d:
                continue
            if a.g != b.g and a.g != a.d and b.g != b.d:
                continue
            u = Unit(
                id=f"U_LOAD_{idx}",
                type="ActiveLoadPair",
                members=[a.name, b.name],
                nets={a.s, a.g, b.g, a.d, b.d, a.b, b.b},
                detect_conf=0.72,
                check_conf=0.68,
                impact_conf=0.68,
            )
            u.why_detected = [
                f"{a.name} and {b.name} share rail-like source {a.s}.",
                f"Drains are separate output/load nodes ({a.d}, {b.d}).",
                "Gate connection suggests mirror/active-load behavior.",
            ]
            units.append(u)
            idx += 1
    return units


def detect_source_followers(mos: Dict[str, Mosfet]) -> List[Unit]:
    units: List[Unit] = []
    idx = 1
    for m in mos.values():
        if not looks_like_supply(m.d):
            continue
        if is_ground(m.s) or looks_like_supply(m.s):
            continue
        u = Unit(
            id=f"U_FOLLOWER_{idx}",
            type="SourceFollower",
            members=[m.name],
            nets={m.d, m.g, m.s, m.b},
            detect_conf=0.66,
            check_conf=0.65,
            impact_conf=0.60,
        )
        u.why_detected = [
            f"{m.name} has drain on rail-like net {m.d}.",
            f"Source {m.s} is a non-rail node, consistent with follower output.",
        ]
        units.append(u)
        idx += 1
    return units
