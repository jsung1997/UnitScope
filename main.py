from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


# ----------------------------
# Data structures
# ----------------------------

@dataclass(frozen=True)
class Mosfet:
    name: str
    d: str
    g: str
    s: str
    b: str
    model: str  # NMOS/PMOS or model name


# ----------------------------
# Netlist parsing (very simple SPICE-style)
# ----------------------------

def parse_netlist_mos(path: Path) -> Dict[str, Mosfet]:
    """
    Parse only MOSFET lines that look like:
      M1 drain gate source bulk model
    Ignores everything else for now.

    Returns dict: mos_name -> Mosfet
    """
    mos: Dict[str, Mosfet] = {}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue

        # Remove inline comments starting with '*'
        if "*" in line:
            line = line.split("*", 1)[0].strip()

        tokens = line.split()
        if not tokens:
            continue

        if tokens[0].startswith("M") and len(tokens) >= 6:
            name = tokens[0]
            d, g, s, b = tokens[1], tokens[2], tokens[3], tokens[4]
            model = tokens[5]
            mos[name] = Mosfet(name=name, d=d, g=g, s=s, b=b, model=model)

    return mos


# ----------------------------
# Diff pair detection
# ----------------------------

@dataclass(frozen=True)
class DiffPair:
    m1: str
    m2: str
    shared_source: str
    gates: Tuple[str, str]
    drains: Tuple[str, str]
    confidence: float


def detect_diff_pairs(mos: Dict[str, Mosfet]) -> List[DiffPair]:
    """
    Very first rule-based diff pair detector.

    Core pattern (simple version):
    - Two MOSFETs of same model type (e.g., both NMOS)
    - Share the same source net
    - Have different gate nets
    - Have different drain nets

    Returns a list of DiffPair objects.
    """
    names = sorted(mos.keys())
    pairs: List[DiffPair] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = mos[names[i]]
            b = mos[names[j]]

            # 1) same type/model (you can later normalize model names)
            if a.model != b.model:
                continue

            # 2) shared source (tail node)
            if a.s != b.s:
                continue

            # 3) gates should differ (two inputs)
            if a.g == b.g:
                continue

            # 4) drains should differ (two outputs)
            if a.d == b.d:
                continue

            # Confidence heuristic (simple, improve later)
            conf = 0.70

            # Increase confidence if bulks match (common in IC schematics)
            if a.b == b.b:
                conf += 0.10

            # Increase confidence if drains look like two separate internal nodes (not supplies)
            # (very crude heuristic)
            if a.d not in ("0", "gnd", "vss") and b.d not in ("0", "gnd", "vss"):
                conf += 0.10

            pairs.append(
                DiffPair(
                    m1=a.name,
                    m2=b.name,
                    shared_source=a.s,
                    gates=(a.g, b.g),
                    drains=(a.d, b.d),
                    confidence=min(conf, 0.95),
                )
            )

    return pairs


# ----------------------------
# Main
# ----------------------------

def main():
    netlist_path = Path("data/examples/diffpair.sp")
    mos = parse_netlist_mos(netlist_path)

    print(f"Parsed MOSFETs: {len(mos)}")
    for m in mos.values():
        print(f"  {m.name}: D={m.d} G={m.g} S={m.s} B={m.b} MODEL={m.model}")

    diff_pairs = detect_diff_pairs(mos)

    print("\nDetected differential pairs:")
    if not diff_pairs:
        print("  (none)")
    for dp in diff_pairs:
        print(
            f"  DiffPair: ({dp.m1}, {dp.m2}) "
            f"shared_source={dp.shared_source} "
            f"gates={dp.gates} drains={dp.drains} "
            f"confidence={dp.confidence:.2f}"
        )


if __name__ == "__main__":
    main()
