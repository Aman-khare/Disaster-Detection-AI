from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def load_dataset() -> dict[str, Any]:
    with (DATA_DIR / "scenarios.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)

