#!/usr/bin/env python3
"""Compute top-10 values by record count for each supply-side field.

Reads the minimal CSV (land-only records with valid coordinates) and
writes one CSV + one LaTeX table per field to Exhibits/tables/.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import (
    EQUAL_AREA_CRS,
    EXHIBIT_TABLES,
    LAND_CELLS_CSV,
    MINIMAL_CSV,
    PROCESSED_BOLD,
    ensure_output_dirs,
)

TARGET_FIELDS = [
    "inst",
    "collection_code",
    "collectors",
    "identified_by",
    "sequence_run_site",
    "funding_src",
]

FIELD_LABELS = {
    "inst": "Depositing Institution",
    "collection_code": "Collection Code",
    "collectors": "Field Collector(s)",
    "identified_by": "Taxonomist (Identifier)",
    "sequence_run_site": "Sequencing Laboratory",
    "funding_src": "Funding Source",
}

INPUT_COLUMNS = ["has_coord", "latitude", "longitude"] + TARGET_FIELDS
CELL_KM = 100
CHUNKSIZE = 500_000
TOP_N = 10


def assign_cells(lat: np.ndarray, lon: np.ndarray, transformer, cell_m: float) -> np.ndarray:
    x, y = transformer.transform(lon, lat)
    cx = np.floor(x / cell_m).astype(int)
    cy = np.floor(y / cell_m).astype(int)
    return np.char.add(np.char.add(cx.astype(str), "_"), cy.astype(str))


def fmt_int(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def escape_latex(s: str) -> str:
    for char, repl in [("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"), ("{", r"\{"), ("}", r"\}")]:
        s = s.replace(char, repl)
    return s


def write_top10_table(field: str, top: list[tuple[str, int]], total: int, path: Path) -> None:
    label = FIELD_LABELS.get(field, field)
    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{rlrr}",
        r"\toprule",
        r"Rank & Value & Records & Share (\%) \\",
        r"\midrule",
    ]
    for rank, (val, cnt) in enumerate(top, 1):
        pct = 100 * cnt / max(total, 1)
        display = escape_latex(val[:70])
        lines.append(f"{rank} & {display} & {cnt:,} & {pct:.1f} \\\\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        f"\\caption{{Top {len(top)} values of \\texttt{{{field.replace('_', chr(92) + '_')}}}"
        f" ({label}) among {fmt_int(total)} non-empty land records.}}",
        f"\\label{{tab:top10_{field}}}",
        r"\end{table}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ensure_output_dirs()

    land_ids = set(pd.read_csv(LAND_CELLS_CSV, dtype=str, usecols=["cell_id"])["cell_id"])
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = CELL_KM * 1000

    counters = {f: Counter() for f in TARGET_FIELDS}
    land_total = 0
    started = time.time()

    for ci, chunk in enumerate(
        pd.read_csv(MINIMAL_CSV, dtype=str, usecols=INPUT_COLUMNS, chunksize=CHUNKSIZE), 1
    ):
        has_coord = chunk["has_coord"].fillna("") == "1"
        sub = chunk.loc[has_coord]
        if sub.empty:
            continue

        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        if valid.sum() == 0:
            continue

        cids = assign_cells(lat[valid].to_numpy(), lon[valid].to_numpy(), transformer, cell_m)
        in_land = pd.Series(cids).isin(land_ids).to_numpy()
        nl = int(in_land.sum())
        land_total += nl
        if nl == 0:
            continue

        valid_idx = sub.index[valid].to_numpy()
        land_idx = valid_idx[in_land]

        for f in TARGET_FIELDS:
            vals = chunk.loc[land_idx, f].fillna("").str.strip()
            vals = vals[vals != ""]
            counters[f].update(vals)

        elapsed = max(time.time() - started, 1)
        print(f"chunk {ci:,}: {land_total:,} land rows ({land_total / elapsed:,.0f}/sec)", flush=True)

    print(f"\nLand records: {land_total:,}", flush=True)
    print(f"Elapsed: {(time.time() - started) / 60:.1f} min\n", flush=True)

    for f in TARGET_FIELDS:
        total_nonempty = sum(counters[f].values())
        if f == "collectors":
            filtered = {k: v for k, v in counters[f].items()
                        if "janzen" not in k.lower() and "hallwachs" not in k.lower()}
            top = Counter(filtered).most_common(TOP_N)
        else:
            top = counters[f].most_common(TOP_N)

        csv_path = PROCESSED_BOLD / f"supply_top10_{f}.csv"
        rows = []
        for rank, (val, cnt) in enumerate(top, 1):
            rows.append({"rank": rank, "value": val, "count": cnt, "pct": round(100 * cnt / max(total_nonempty, 1), 2)})
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        tex_path = EXHIBIT_TABLES / f"supply_top10_{f}.tex"
        write_top10_table(f, top, total_nonempty, tex_path)

        print(f"{f}: {total_nonempty:,} non-empty, {len(counters[f]):,} unique")
        for rank, (val, cnt) in enumerate(top, 1):
            print(f"  {rank:2d}. {cnt:>10,} ({100*cnt/max(total_nonempty,1):5.1f}%)  {val[:80]}")
        print()

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
