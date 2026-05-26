from __future__ import annotations

from pathlib import Path

import pandas as pd


def _write_optional_csv(result: pd.DataFrame, output_csv: str | Path | None) -> None:
    if output_csv is None:
        return
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(path, index=False)
