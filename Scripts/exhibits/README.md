# Exhibit Scripts

Run from the project root:

```bash
cd /Users/vasilykorovkin/Documents/Diversity_Discoveries
```

Run order:

```bash
python3 Scripts/exhibits/00_build_bold_minimal.py
python3 Scripts/exhibits/01_tables_counts.py
python3 Scripts/exhibits/02_timeseries.py
python3 Scripts/exhibits/03_maps_grid.py
python3 Scripts/exhibits/04_maps_admin1.py
python3 Scripts/exhibits/05_cell_correlations.py
python3 Scripts/exhibits/06_build_cell_year_panel.py
```

`00_build_bold_minimal.py` is the expensive step because it streams the raw
BOLD TSV files. The later scripts read compact files in `Exhibits/data/`.

The default source selection includes the capped Costa Rica Cecidomyiidae file,
because otherwise that major sampling cluster is absent. It still excludes the
global capped Cecidomyiidae diagnostic file and the old capped order-level
Hemiptera file. Diptera remains incomplete for Costa Rica Cecidomyiidae because
BOLD caps that country-family request at 1M records.

Outputs:

```text
Exhibits/data/
Exhibits/tables/
Exhibits/figures/
Exhibits/maps/
```

Maps use raw record counts with logarithmic color scales. Correlation tables
use all 100 km land cells and therefore include true zero-sampling cells.
The cell-year panel uses BOLD sequence upload year, 2005-2025, and includes all
100 km land cells x years with zeros.
