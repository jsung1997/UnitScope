from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from .config import PdkConfig, active_pdk_config, set_active_pdk_config
from .models import Mosfet, Passive
from .utils import infer_mos_type, parse_spice_number


def _strip_inline_comment(line: str) -> str:
    for marker in ("//", ";"):
        if marker in line:
            line = line.split(marker, 1)[0]
    if "*" in line:
        line = line.split("*", 1)[0]
    return line.strip()


def _logical_lines(text: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    current = ""
    start_line = 0

    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("*"):
            continue

        if stripped.startswith("+"):
            current += " " + _strip_inline_comment(stripped[1:])
            continue

        if current:
            out.append((start_line, current.strip()))

        start_line = line_no
        current = _strip_inline_comment(stripped)

    if current:
        out.append((start_line, current.strip()))

    return out


def _parse_params(tokens: List[str]) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for tok in tokens:
        if "=" not in tok:
            continue
        key, value = tok.split("=", 1)
        params[key.strip().lower()] = value.strip()
    return params


def _param_float(params: Dict[str, str], names: List[str]) -> float | None:
    for name in names:
        if name in params:
            return parse_spice_number(params[name])
    return None


def _param_float_default(params: Dict[str, str], default: float, names: List[str]) -> float:
    value = _param_float(params, names)
    return default if value is None else value


def parse_netlist(path: Path, config: PdkConfig | None = None) -> Tuple[Dict[str, Mosfet], Dict[str, Passive]]:
    """
    SPICE/CDL-oriented parser for static structure analysis.

    Supports:
      - MOSFET lines: Mname d g s b model
      - Resistor lines: Rname n1 n2 value
      - Capacitor lines: Cname n1 n2 value
      - .SUBCKT/.ENDS hierarchy labels
      - continuation lines beginning with '+'
      - common key=value device parameters

    Ignores unsupported simulator directives and device classes.
    """
    cfg = config or active_pdk_config()
    set_active_pdk_config(cfg)
    mos: Dict[str, Mosfet] = {}
    pas: Dict[str, Passive] = {}

    subckt_stack = ["TOP"]
    for line_no, line in _logical_lines(path.read_text(encoding="utf-8")):
        toks = line.split()
        if not toks:
            continue

        head = toks[0]
        directive = head.lower()
        if directive == ".subckt" and len(toks) >= 2:
            subckt_stack.append(toks[1])
            continue
        if directive == ".ends":
            if len(subckt_stack) > 1:
                subckt_stack.pop()
            continue
        if directive.startswith("."):
            continue

        kind = head[0].upper()
        subckt = subckt_stack[-1]

        if kind == "M" and len(toks) >= 6:
            name = toks[0]
            d, g, s, b = toks[1], toks[2], toks[3], toks[4]
            model = toks[5]
            if model.strip().lower() in cfg.ignored_models:
                continue
            params = _parse_params(toks[6:])
            key = f"{subckt}/{name}" if subckt != "TOP" else name
            mos[key] = Mosfet(
                name=key,
                d=d,
                g=g,
                s=s,
                b=b,
                model=model,
                params=params,
                device_type=infer_mos_type(model, name, cfg),
                w=_param_float(params, cfg.width_params),
                l=_param_float(params, cfg.length_params),
                m=_param_float_default(params, 1.0, cfg.multiplier_params),
                nf=_param_float_default(params, 1.0, cfg.finger_params + cfg.fin_params),
                subckt=subckt,
                line_no=line_no,
                raw=line,
            )
            continue

        if kind in ("R", "C") and len(toks) >= 4:
            name = toks[0]
            n1, n2, value = toks[1], toks[2], toks[3]
            params = _parse_params(toks[4:])
            key = f"{subckt}/{name}" if subckt != "TOP" else name
            pas[key] = Passive(
                name=key,
                n1=n1,
                n2=n2,
                value=value,
                kind=kind,
                params=params,
                numeric_value=parse_spice_number(value),
                subckt=subckt,
                line_no=line_no,
                raw=line,
            )
            continue

    return mos, pas
