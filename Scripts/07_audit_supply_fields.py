#!/usr/bin/env python3
"""Audit coverage of supply-side metadata fields in the BOLD minimal CSV.

Reports non-missing record counts, cell coverage, and cardinality for
inst, collectors, identified_by, collection_code, sequence_run_site,
and funding_src.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from pipeline_utils import (
    EQUAL_AREA_CRS,
    PROCESSED_BOLD,
    EXHIBIT_TABLES,
    LAND_CELLS_CSV,
    MINIMAL_CSV,
    ensure_output_dirs,
    iter_minimal_chunks,
)

TARGET_FIELDS = [
    "inst",
    "collection_code",
    "collectors",
    "identified_by",
    "sequence_run_site",
    "funding_src",
]
CELL_KM = 100
CHUNKSIZE = 500_000

INPUT_COLUMNS = [
    "has_coord",
    "latitude",
    "longitude",
] + TARGET_FIELDS


def assign_cells(lat: np.ndarray, lon: np.ndarray, transformer, cell_m: float) -> np.ndarray:
    x, y = transformer.transform(lon, lat)
    cx = np.floor(x / cell_m).astype(int)
    cy = np.floor(y / cell_m).astype(int)
    return np.char.add(np.char.add(cx.astype(str), "_"), cy.astype(str))


FIELD_LABELS = {
    "inst": "Depositing institution",
    "collection_code": "Sub-institutional collection",
    "collectors": "Field collector(s)",
    "identified_by": "Taxonomist (identifier)",
    "sequence_run_site": "Sequencing laboratory",
    "funding_src": "Funding organization",
}


def fmt_int(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def write_latex_table(df: pd.DataFrame, total: int, land_total: int, n_cells: int, path: Path) -> None:
    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Field & Content & Non-miss.\ (\%) & Unique & Cells & Cell \% \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        f = row["field"]
        label = FIELD_LABELS.get(f, f)
        lines.append(
            f"\\texttt{{{f.replace('_', chr(92) + '_')}}} & "
            f"{label} & "
            f"{fmt_int(int(row['nonempty_land']))} ({row['pct_land']:.0f}\\%) & "
            f"{fmt_int(int(row['n_unique_land']))} & "
            f"{int(row['cells_with_field']):,} & "
            f"{row['pct_cells']:.0f}\\% \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        f"\\caption{{Coverage of supply-side metadata fields among {fmt_int(land_total)} "
        f"BOLD records in {n_cells:,} land cells (100\\,km grid).}}",
        r"\label{tab:supply_field_audit}",
        r"\end{table}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote LaTeX table: {path}", flush=True)


def main() -> int:
    ensure_output_dirs()
    output = PROCESSED_BOLD / "bold_supply_field_audit.csv"

    land_ids = set(pd.read_csv(LAND_CELLS_CSV, dtype=str, usecols=["cell_id"])["cell_id"])
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    cell_m = CELL_KM * 1000

    print(f"Input: {MINIMAL_CSV}", flush=True)
    print(f"Land cells: {len(land_ids):,}", flush=True)

    total = 0
    coord_total = 0
    land_total = 0
    ne_all = {f: 0 for f in TARGET_FIELDS}
    ne_land = {f: 0 for f in TARGET_FIELDS}
    cells_with = {f: set() for f in TARGET_FIELDS}
    unique_vals = {f: set() for f in TARGET_FIELDS}
    cells_any = set()
    started = time.time()

    for chunk_index, chunk in enumerate(
        pd.read_csv(MINIMAL_CSV, dtype=str, usecols=INPUT_COLUMNS, chunksize=CHUNKSIZE), 1
    ):
        n = len(chunk)
        total += n

        for f in TARGET_FIELDS:
            vals = chunk[f].fillna("").str.strip()
            ne_all[f] += int((vals != "").sum())

        has_coord = chunk["has_coord"].fillna("") == "1"
        sub = chunk.loc[has_coord]
        if sub.empty:
            continue

        lat = pd.to_numeric(sub["latitude"], errors="coerce")
        lon = pd.to_numeric(sub["longitude"], errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        nv = int(valid.sum())
        coord_total += nv
        if nv == 0:
            continue

        cids = assign_cells(lat[valid].to_numpy(), lon[valid].to_numpy(), transformer, cell_m)
        in_land = pd.Series(cids).isin(land_ids).to_numpy()
        nl = int(in_land.sum())
        land_total += nl
        if nl == 0:
            continue

        land_cids = cids[in_land]
        cells_any.update(land_cids)

        valid_idx = sub.index[valid].to_numpy()
        land_orig_idx = valid_idx[in_land]
        for f in TARGET_FIELDS:
            vals = chunk.loc[land_orig_idx, f].fillna("").str.strip()
            ne_mask = vals != ""
            cnt = int(ne_mask.sum())
            ne_land[f] += cnt
            if cnt:
                cells_with[f].update(land_cids[ne_mask.to_numpy()])
                unique_vals[f].update(vals[ne_mask])

        elapsed = max(time.time() - started, 1)
        print(
            f"chunk {chunk_index:,}: {total:,} rows  "
            f"({total / elapsed:,.0f}/sec)",
            flush=True,
        )

    elapsed = max(time.time() - started, 1)
    n_cells = len(cells_any)
    print(f"\nRows: {total:,}  Coord: {coord_total:,}  Land: {land_total:,}  Cells: {n_cells:,}", flush=True)
    print(f"Elapsed: {elapsed / 60:.1f} min\n", flush=True)

    rows = []
    for f in TARGET_FIELDS:
        r = {
            "field": f,
            "nonempty_all": ne_all[f],
            "pct_all": round(100 * ne_all[f] / max(total, 1), 1),
            "nonempty_land": ne_land[f],
            "pct_land": round(100 * ne_land[f] / max(land_total, 1), 1),
            "n_unique_land": len(unique_vals[f]),
            "cells_with_field": len(cells_with[f]),
            "cells_any_record": n_cells,
            "pct_cells": round(100 * len(cells_with[f]) / max(n_cells, 1), 1),
        }
        rows.append(r)
        print(
            f"{f:25s}  all:{r['nonempty_all']:>12,} ({r['pct_all']:5.1f}%)  "
            f"land:{r['nonempty_land']:>12,} ({r['pct_land']:5.1f}%)  "
            f"uniq:{r['n_unique_land']:>8,}  "
            f"cells:{r['cells_with_field']:>6,}/{n_cells:,} ({r['pct_cells']:5.1f}%)",
            flush=True,
        )

    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
    print(f"\nWrote: {output}", flush=True)

    tex_path = EXHIBIT_TABLES / "supply_field_audit.tex"
    write_latex_table(df, total, land_total, n_cells, tex_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
