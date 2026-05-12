# Scripts Layout

The script folder is organized by role:

- `download/`: raw-data downloads and API request scripts.
- `preliminary/`: audits, summaries, probes, mapping diagnostics, and early-stage data preparation.
- `aggregate/`: spatial/temporal aggregation and Earth Engine export merge scripts.
- `pipeline/`: main derived-panel and analysis-input builders.
- `earth_engine/`: Google Earth Engine JavaScript request files.
- `readmes/`: workflow notes and source-specific READMEs.
- `_shared/`: Python helper modules imported by the executable scripts.

Run commands from the project root, for example:

```bash
python3 Scripts/pipeline/00_build_bold_minimal.py
python3 Scripts/aggregate/aggregate_ucdp_ged_100km.py
python3 Scripts/download/download_chirps.py --skip-existing
```

Detailed workflow notes are in `Scripts/readmes/scripts_workflow_README.md`.
