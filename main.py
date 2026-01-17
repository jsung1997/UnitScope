from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# =========================
# Data structures
# =========================

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
    model: str  # "NMOS", "PMOS", or a model name


@dataclass(frozen=True)
class Passive:
    name: str
    n1: str
    n2: str
    value: str
    kind: str  # "R" or "C"


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

    # These will be filled after checks
    likelihood: float = 0.0
    impact: float = 0.0
    confidence: float = 0.0
    risk: float = 0.0

    # Evidence for explainability
    why_detected: List[str] = field(default_factory=list)
    checks: List[dict] = field(default_factory=list)
    explanation: str = ""


# =========================
# Helpers
# =========================

def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def is_ground(net: str) -> bool:
    n = net.strip().lower()
    return n in ("0", "gnd", "vss", "ground")


def looks_like_supply(net: str) -> bool:
    n = net.strip().lower()
    # very rough heuristic
    return n in ("vdd", "vcc", "vp", "vn", "vss", "gnd", "0") or n.startswith("vdd") or n.startswith("vss")


def unit_type_impact(unit_type: str) -> float:
    # Simple prior: bias-related units tend to have higher systemic impact
    table = {
        "BiasNetwork": 1.00,
        "CurrentMirror": 0.90,
        "DiffPair": 0.70,
        "DiodeConnected": 0.50,
    }
    return table.get(unit_type, 0.50)


def unit_importance_for_spread(unit_type: str) -> float:
    # How much downstream units count in blast radius
    table = {
        "BiasNetwork": 1.0,
        "CurrentMirror": 0.9,
        "DiffPair": 0.6,
        "DiodeConnected": 0.4,
    }
    return table.get(unit_type, 0.5)


# =========================
# Netlist parsing (minimal)
# =========================

def parse_netlist(path: Path) -> Tuple[Dict[str, Mosfet], Dict[str, Passive]]:
    """
    Parse a simple SPICE-like netlist.
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

        # Remove inline comments starting with '*'
        if "*" in line:
            line = line.split("*", 1)[0].strip()

        toks = line.split()
        if not toks:
            continue

        head = toks[0]

        # MOSFET
        if head[0].upper() == "M" and len(toks) >= 6:
            name = toks[0]
            d, g, s, b = toks[1], toks[2], toks[3], toks[4]
            model = toks[5]
            mos[name] = Mosfet(name=name, d=d, g=g, s=s, b=b, model=model)
            continue

        # Resistor / Capacitor
        if head[0].upper() in ("R", "C") and len(toks) >= 4:
            kind = head[0].upper()
            name = toks[0]
            n1, n2, value = toks[1], toks[2], toks[3]
            pas[name] = Passive(name=name, n1=n1, n2=n2, value=value, kind=kind)
            continue

    return mos, pas


# =========================
# Unit detection
# =========================

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
            u.why_detected = [
                f"{m.name} is diode-connected because gate == drain ({m.g})."
            ]
            units.append(u)
            idx += 1
    return units


def detect_current_mirrors(mos: Dict[str, Mosfet]) -> List[Unit]:
    """
    Detect simple 2-transistor current mirrors:
      - Mx diode-connected (g == d)
      - My shares gate with Mx, and shares source with Mx
      - same model type
    """
    units: List[Unit] = []
    names = sorted(mos.keys())
    idx = 1

    # Find diode candidates first
    diode = {n for n, m in mos.items() if m.g == m.d}

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

            # avoid mirrors to obvious supplies only (weak heuristic)
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
    Detect simple MOS differential pairs:
      - same model
      - share source node
      - different gate nodes
      - different drain nodes
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

            # confidence heuristic
            conf = 0.75
            if a.b == b.b:
                conf += 0.10
            if not looks_like_supply(a.d) and not looks_like_supply(b.d):
                conf += 0.05

            u = Unit(
                id=f"U_DIFF_{idx}",
                type="DiffPair",
                members=[a.name, b.name],
                nets={a.s, a.g, b.g, a.d, b.d, a.b, b.b},
                detect_conf=clip(conf, 0.5, 0.95),
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


# =========================
# Dependency graph (unit -> unit)
# =========================

def build_unit_dependency_graph(units: List[Unit], mos: Dict[str, Mosfet]) -> Dict[str, Set[str]]:
    """
    Build a rough unit dependency graph using a practical heuristic:

    If a CurrentMirror's shared gate net appears as a gate net in MOSFETs
    belonging to another unit, we say mirror "biases" that unit.

    This is NOT perfect analog semantics, but it is enough to demonstrate:
      - blast radius
      - ranking by impact
    """
    # map device -> unit_id (if a device belongs to multiple units, last wins; ok for MVP)
    dev2unit: Dict[str, str] = {}
    for u in units:
        for d in u.members:
            dev2unit[d] = u.id

    # precompute: unit_id -> set of gate nets used by member MOSFETs
    unit_gate_nets: Dict[str, Set[str]] = {u.id: set() for u in units}
    for u in units:
        for dev in u.members:
            if dev in mos:
                unit_gate_nets[u.id].add(mos[dev].g)

    # dependencies adjacency
    deps: Dict[str, Set[str]] = {u.id: set() for u in units}

    # For each mirror, connect to units that use mirror gate net on their transistors
    for u in units:
        if u.type != "CurrentMirror":
            continue

        # mirror gate net = diode transistor gate (they share gate)
        mirror_gate_nets = set()
        for dev in u.members:
            if dev in mos:
                mirror_gate_nets.add(mos[dev].g)

        # find units that contain MOSFETs whose gate net is one of mirror gate nets
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
    """
    Simple 'single-point of failure' bonus:
    - if a unit directly biases many units, treat as more critical.
    """
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


# =========================
# Health checks (structural proxies)
# =========================

def run_health_checks(u: Unit, mos: Dict[str, Mosfet], deps: Dict[str, Set[str]]) -> List[dict]:
    """
    Returns list of checks:
      {name, severity (0-1), weight, observed, expected, severity_label}
    This is intentionally explainable and tunable.
    """

    checks: List[dict] = []

    # --- Common checks: Fanout/loading ---
    fanout = len(deps.get(u.id, set()))
    # Severity rises with fanout; saturate around 5
    fanout_sev = clip(fanout / 5.0)
    checks.append({
        "name": "LoadFanout",
        "severity": fanout_sev,
        "weight": 0.20,
        "observed": f"fanout={fanout}",
        "expected": "lower is safer (<=2 ideal)",
        "severity_label": _label_sev(fanout_sev),
    })

    # --- Unit-specific checks ---
    if u.type == "CurrentMirror":
        # Headroom proxy: mirrors often fail with stacking / low supply margin,
        # but we don't have voltages. Use structural proxy:
        # - if mirror drains connect to supplies a lot, treat as less risky
        # - if output drain looks like internal node, treat as more sensitive to Vds.
        members = [mos[m] for m in u.members if m in mos]
        out_drains = [m.d for m in members]

        internal_outputs = sum(1 for d in out_drains if not looks_like_supply(d) and not is_ground(d))
        # if both drains are internal -> more risk
        headroom_sev = clip(internal_outputs / 2.0)
        checks.append({
            "name": "HeadroomProxy",
            "severity": headroom_sev,
            "weight": 0.35,
            "observed": f"internal_output_drains={internal_outputs}/2 ({out_drains})",
            "expected": "outputs with low headroom tend to be risky",
            "severity_label": _label_sev(headroom_sev),
        })

        # Single-point-of-failure proxy: mirror gate biases multiple units
        spof = spof_bonus(u.id, deps)
        spof_sev = clip(spof / 0.20)
        checks.append({
            "name": "SinglePointFailure",
            "severity": spof_sev,
            "weight": 0.15,
            "observed": f"spof_bonus={spof:.2f} (based on fanout)",
            "expected": "lower is safer",
            "severity_label": _label_sev(spof_sev),
        })

        # Sensitivity proxy: if mirror gate net is used widely, risk of noise coupling rises
        # We'll approximate by fanout again, but with lower weight; real system later uses net classification.
        sens_sev = clip(fanout / 6.0)
        checks.append({
            "name": "BiasSensitivityProxy",
            "severity": sens_sev,
            "weight": 0.20,
            "observed": f"bias_gate_used_by_units={fanout}",
            "expected": "bias nets should be stable/isolated",
            "severity_label": _label_sev(sens_sev),
        })

    elif u.type == "DiffPair":
        # Mismatch/symmetry proxy: if bulks differ or one drain is a supply, suspicious
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
            "expected": "diff pairs usually rely on symmetry/matching",
            "severity_label": _label_sev(mismatch_sev),
        })

        # Tail dependency proxy: if source node is ground, it’s probably not a real diff pair tail
        tail = a.s
        tail_sev = 0.0
        if is_ground(tail):
            tail_sev = 0.9
        checks.append({
            "name": "TailNodeProxy",
            "severity": tail_sev,
            "weight": 0.35,
            "observed": f"tail_node={tail}",
            "expected": "tail node typically is a bias-controlled node, not ground",
            "severity_label": _label_sev(tail_sev),
        })

        # Dependency risk: if a mirror biases this diff pair, diff pair inherits some risk
        # We'll approximate: number of incoming mirrors not modeled; for MVP, use fanout=0 and keep it light.
        checks.append({
            "name": "BiasDependencyProxy",
            "severity": 0.2 if fanout == 0 else 0.3,
            "weight": 0.20,
            "observed": "heuristic",
            "expected": "diff pairs depend on stable biasing",
            "severity_label": "low",
        })

    elif u.type == "DiodeConnected":
        # diode devices are usually part of biasing; treat internal-node diode connections as more sensitive
        m = mos[u.members[0]]
        sev = 0.2
        if not looks_like_supply(m.g) and not is_ground(m.g):
            sev = 0.5
        checks.append({
            "name": "DiodeSensitivityProxy",
            "severity": sev,
            "weight": 0.25,
            "observed": f"diode_node={m.g}",
            "expected": "diode-connected references can be sensitive",
            "severity_label": _label_sev(sev),
        })

    else:
        # default small check so likelihood isn't always zero
        checks.append({
            "name": "GenericProxy",
            "severity": 0.2,
            "weight": 0.2,
            "observed": "n/a",
            "expected": "n/a",
            "severity_label": "low",
        })

    return checks


def _label_sev(sev: float) -> str:
    if sev >= 0.8:
        return "high"
    if sev >= 0.5:
        return "medium"
    if sev >= 0.25:
        return "low"
    return "very_low"


# =========================
# Ranking logic (Likelihood × Impact × Confidence)
# =========================

def compute_scores(units: List[Unit], mos: Dict[str, Mosfet], deps: Dict[str, Set[str]]) -> None:
    """
    Mutates Unit objects: fills likelihood, impact, confidence, risk, explanation, checks.
    """
    # Precompute for spread
    unit_by_id = {u.id: u for u in units}

    for u in units:
        checks = run_health_checks(u, mos, deps)
        u.checks = checks

        # Likelihood = weighted sum of check severities
        L = 0.0
        for c in checks:
            L += c["severity"] * c["weight"]
        L = clip(L)
        u.likelihood = L

        # Impact:
        #  - spread: how many (and how important) downstream units depend on this unit
        reach = reachable_units(deps, u.id)
        spread_weight = sum(unit_importance_for_spread(unit_by_id[v].type) for v in reach if v in unit_by_id)
        I_spread = 1 - math.exp(-0.4 * spread_weight)  # diminishing returns
        I_type = unit_type_impact(u.type)
        I_spof = spof_bonus(u.id, deps)

        I = clip(0.5 * I_spread + 0.4 * I_type + 0.1 * (I_spof / 0.20 if I_spof > 0 else 0.0))
        u.impact = I

        # Confidence = weighted mix
        C = clip(0.5 * u.detect_conf + 0.3 * u.check_conf + 0.2 * u.impact_conf)
        u.confidence = C

        # Risk = L × I × C
        u.risk = clip(L * I * C)

        # Explanation: top 2-3 reasons
        top = sorted(checks, key=lambda x: x["severity"] * x["weight"], reverse=True)[:3]
        reasons = "; ".join([f"{t['name']}={t['severity_label']} ({t['observed']})" for t in top])

        # blast radius summary
        if len(reach) == 0:
            blast = "limited downstream dependencies"
        else:
            blast = f"affects {len(reach)} downstream unit(s): {', '.join(sorted(list(reach))[:5])}" + ("..." if len(reach) > 5 else "")

        u.explanation = (
            f"Risk={u.risk:.2f} because {reasons}. Impact: {blast}."
        )


def rank_weak_points(units: List[Unit]) -> List[Unit]:
    return sorted(units, key=lambda u: u.risk, reverse=True)


# =========================
# Main entry
# =========================

def main():
    netlist_path = Path("data/examples/sample.sp")
    if not netlist_path.exists():
        print("Missing netlist file:", netlist_path)
        print("Create it using the sample in the instructions below.")
        return

    mos, pas = parse_netlist(netlist_path)

    print("=== Parsed ===")
    print(f"MOSFETs: {len(mos)}")
    for m in mos.values():
        print(f"  {m.name}: D={m.d} G={m.g} S={m.s} B={m.b} MODEL={m.model}")
    print(f"Passives: {len(pas)}")
    for p in pas.values():
        print(f"  {p.name}: {p.kind} {p.n1}-{p.n2} {p.value}")

    # Detect units
    units: List[Unit] = []
    units += detect_diode_connected(mos)
    units += detect_current_mirrors(mos)
    units += detect_diff_pairs(mos)

    # If you want to treat "mirror group" as a BiasNetwork when there are multiple mirrors sharing a gate net,
    # you can add that later. For now, mirror itself is the bias-ish unit.

    print("\n=== Detected Units ===")
    for u in units:
        print(f"  {u.id} {u.type} members={u.members}")

    # Dependency graph
    deps = build_unit_dependency_graph(units, mos)
    print("\n=== Unit Dependency Graph (who biases whom, heuristic) ===")
    any_edges = False
    for uid, outs in deps.items():
        if outs:
            any_edges = True
            print(f"  {uid} -> {sorted(list(outs))}")
    if not any_edges:
        print("  (no dependencies inferred yet)")

    # Score and rank weak points
    compute_scores(units, mos, deps)
    ranked = rank_weak_points(units)

    print("\n=== Ranked Weak Points ===")
    for i, u in enumerate(ranked, start=1):
        print(f"\n#{i} {u.id} [{u.type}]  risk={u.risk:.2f}  (L={u.likelihood:.2f}, I={u.impact:.2f}, C={u.confidence:.2f})")
        print("Members:", ", ".join(u.members))
        print("Why detected:")
        for w in u.why_detected[:4]:
            print("  -", w)
        print("Top checks:")
        top = sorted(u.checks, key=lambda x: x["severity"] * x["weight"], reverse=True)[:3]
        for c in top:
            print(f"  - {c['name']}: severity={c['severity']:.2f} ({c['severity_label']}), observed={c['observed']}")
        print("Explanation:")
        print(" ", u.explanation)

    print("\nDone.")


if __name__ == "__main__":
    main()
