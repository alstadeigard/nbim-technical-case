"""
Minimal config loader kept for formatting knobs only.
Risk scoring is deterministic and does not depend on config.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


_DEFAULTS: Dict[str, Any] = {
    "formatting": {
        "rounding": {
            "amounts_dp": 2,
            "fx_dp": 6,
        }
    },
}


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.exists(path) or yaml is None:
        return dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        fmt = dict(_DEFAULTS["formatting"])
        fmt.update(user_cfg.get("formatting", {})) if isinstance(user_cfg, dict) else None
        return {"formatting": fmt}
    except Exception:
        return dict(_DEFAULTS)


def rounding(cfg: Dict[str, Any], key: str) -> int:
    return int(cfg.get("formatting", {}).get("rounding", {}).get(key, _DEFAULTS["formatting"]["rounding"][key]))
