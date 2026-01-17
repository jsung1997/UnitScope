from __future__ import annotations

from pathlib import Path

from engine.parser import parse_netlist
from engine.units_detect import detect_diode_connected, detect_current_mirrors, detect_diff_pairs
from engine.dependency import build_unit_dependency_graph
from engine.ranking import compute_scores, rank_weak_points


def main():
    netlist_path = Path("data/examples/sample.sp")
    if not netlist_path.exists():
        print("Missing netlist file:", netlist_path)
        print("Create it using the sample below.")
        return

    mos, pas = parse_netlist(netlist_path)

    print("=== Parsed ===")
    print(f"MOSFETs: {len(mos)}")
    for m in mos.values():
        print(f"  {m.name}: D={m.d} G={m.g} S={m.s} B={m.b} MODEL={m.model}")
    print(f"Passives: {len(pas)}")

    # Detect units
    units = []
    units += detect_diode_connected(mos)
    units += detect_current_mirrors(mos)
    units += detect_diff_pairs(mos)

    print("\n=== Detected Units ===")
    for u in units:
        print(f"  {u.id} {u.type} members={u.members}")

    # Dependencies
    deps = build_unit_dependency_graph(units, mos)
    print("\n=== Dependency Graph (heuristic) ===")
    any_edges = False
    for uid, outs in deps.items():
        if outs:
            any_edges = True
            print(f"  {uid} -> {sorted(list(outs))}")
    if not any_edges:
        print("  (no dependencies inferred yet)")

    # Score & rank
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
