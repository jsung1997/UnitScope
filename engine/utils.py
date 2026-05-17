from __future__ import annotations

import re

from .config import PdkConfig, active_pdk_config


def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _matches_any(text: str, patterns: list[str]) -> bool:
    value = text.strip().lower()
    return any(value == p or value.startswith(p) for p in patterns)


def is_ground(net: str, config: PdkConfig | None = None) -> bool:
    cfg = config or active_pdk_config()
    n = net.strip().lower()
    return _matches_any(n, cfg.ground_nets)


def looks_like_supply(net: str, config: PdkConfig | None = None) -> bool:
    cfg = config or active_pdk_config()
    n = net.strip().lower()
    return _matches_any(n, cfg.supply_nets) or _matches_any(n, cfg.ground_nets)


def label_severity(sev: float) -> str:
    if sev >= 0.8:
        return "high"
    if sev >= 0.5:
        return "medium"
    if sev >= 0.25:
        return "low"
    return "very_low"


_SPICE_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


def parse_spice_number(value: str) -> float | None:
    """Parse common SPICE numeric suffixes. Returns None for expressions."""
    text = value.strip().strip("{}'\"").lower()
    if not text:
        return None

    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)([a-z]+)?", text)
    if not match:
        return None

    base = float(match.group(1))
    suffix = match.group(2) or ""
    if suffix in _SPICE_SUFFIX:
        return base * _SPICE_SUFFIX[suffix]
    if suffix and suffix[0] in _SPICE_SUFFIX:
        return base * _SPICE_SUFFIX[suffix[0]]
    if suffix:
        return None
    return base


def infer_mos_type(model: str, name: str = "", config: PdkConfig | None = None) -> str:
    cfg = config or active_pdk_config()
    text = f"{name} {model}".lower()
    if any(x in text for x in cfg.pmos_models):
        return "pmos"
    if any(x in text for x in cfg.nmos_models):
        return "nmos"
    return "unknown"


def equivalent_width(w: float | None, m: float = 1.0, nf: float = 1.0) -> float | None:
    if w is None:
        return None
    return w * max(m, 1.0) * max(nf, 1.0)


def rel_delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    den = max(abs(a), abs(b), 1e-30)
    return abs(a - b) / den
