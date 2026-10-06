"""設定ファイルの読み込み。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or (ROOT / "config.yaml")
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"設定ファイルの形式が不正です: {config_path}")
    return data


def abs_path(config: dict[str, Any], key_path: str) -> Path:
    """storage.sqlite_path のようなドット区切りでパスを取り、プロジェクト直下の絶対パスにする。"""
    node: Any = config
    for key in key_path.split("."):
        node = node[key]
    path = Path(str(node))
    if not path.is_absolute():
        path = ROOT / path
    return path
