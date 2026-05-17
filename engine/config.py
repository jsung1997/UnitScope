from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PdkConfig:
    name: str = "Generic SPICE/CDL"
    nmos_models: list[str] = field(default_factory=lambda: ["nmos", "nch", "nfet", "nch_lvt", "nch_rvt"])
    pmos_models: list[str] = field(default_factory=lambda: ["pmos", "pch", "pfet", "pch_lvt", "pch_rvt"])
    supply_nets: list[str] = field(default_factory=lambda: ["vdd", "vdda", "avdd", "dvdd", "vcc", "vp"])
    ground_nets: list[str] = field(default_factory=lambda: ["0", "gnd", "ground", "vss", "vssa", "avss", "dvss", "vn"])
    width_params: list[str] = field(default_factory=lambda: ["w", "width"])
    length_params: list[str] = field(default_factory=lambda: ["l", "length"])
    multiplier_params: list[str] = field(default_factory=lambda: ["m", "mult"])
    finger_params: list[str] = field(default_factory=lambda: ["nf", "fingers"])
    fin_params: list[str] = field(default_factory=lambda: ["nfin", "fins"])
    ignored_models: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PdkConfig":
        base = cls()
        valid = asdict(base)
        cleaned: dict[str, Any] = {}
        for key, default in valid.items():
            value = data.get(key, default)
            if isinstance(default, list):
                cleaned[key] = normalize_list(value)
            else:
                cleaned[key] = str(value).strip() or default
        return cls(**cleaned)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw = value
    else:
        raw = [value]

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip().lower()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "config" / "default_pdk.json"


def load_pdk_config(path: str | Path | None = None) -> PdkConfig:
    cfg_path = Path(path) if path else default_config_path()
    if not cfg_path.exists():
        return PdkConfig()
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"PDK config must be a JSON object: {cfg_path}")
    return PdkConfig.from_dict(data)


_ACTIVE_CONFIG = PdkConfig()


def set_active_pdk_config(config: PdkConfig) -> None:
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = config


def active_pdk_config() -> PdkConfig:
    return _ACTIVE_CONFIG
