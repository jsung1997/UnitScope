from __future__ import annotations


def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def is_ground(net: str) -> bool:
    n = net.strip().lower()
    return n in ("0", "gnd", "vss", "ground")


def looks_like_supply(net: str) -> bool:
    n = net.strip().lower()
    return n in ("vdd", "vcc", "vp", "vn", "vss", "gnd", "0") or n.startswith("vdd") or n.startswith("vss")


def label_severity(sev: float) -> str:
    if sev >= 0.8:
        return "high"
    if sev >= 0.5:
        return "medium"
    if sev >= 0.25:
        return "low"
    return "very_low"
