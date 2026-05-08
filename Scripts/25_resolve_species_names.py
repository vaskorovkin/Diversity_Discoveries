#!/usr/bin/env python3
"""Resolve species names via GBIF backbone taxonomy + finalize NP-DB outputs.

Maps every species name from the NP databases and the shared species
universe to a canonical accepted name, so downstream joins operate on
harmonized names rather than raw input strings.

Resolution priority:
  1. gbifid_lookup   — LOTUS organism_taxonomy_gbifid → backbone taxonID
  2. name_match_exact — lower-cased canonicalName in Taxon.tsv
  3. name_match_fuzzy — GBIF /v1/species/match API (NP-DB names only)
  4. unresolved       — no match found

Also finalizes the NP-DB outputs originally written by Script 23: applies
species-level kingdom backfill (via resolution) and genus-level backfill
(via genus_to_kingdom map; cross-kingdom homonyms excluded), then rewrites
species_compound_pairs.csv and species_to_compounds.csv with completed
kingdoms.

Inputs:
  Data/raw/gbif/backbone/backbone.zip  (Taxon.tsv inside)
  Data/raw/natural_products/lotus/260413_frozen_metadata.csv.gz
  Data/processed/discovery/natural_products/species_to_compounds.csv  (from 23)
  Data/processed/discovery/natural_products/species_compound_pairs.csv (from 23)
  Data/processed/discovery/shared/shared_species_universe.csv

Outputs:
  Data/processed/discovery/shared/species_name_resolution.csv
  Data/processed/discovery/shared/genus_to_kingdom.csv
  Data/processed/discovery/natural_products/species_compound_pairs.csv  (rewritten)
  Data/processed/discovery/natural_products/species_to_compounds.csv    (rewritten)

Usage:
  python3 Scripts/25_resolve_species_names.py
  python3 Scripts/25_resolve_species_names.py --skip-api
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path("/Users/vasilykorovkin/Documents/Diversity_Discoveries")

DEFAULT_BACKBONE = PROJECT_ROOT / "Data" / "raw" / "gbif" / "backbone" / "backbone.zip"
DEFAULT_LOTUS_META = (
    PROJECT_ROOT
    / "Data"
    / "raw"
    / "natural_products"
    / "lotus"
    / "260413_frozen_metadata.csv.gz"
)
DEFAULT_NP = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "natural_products"
    / "species_to_compounds.csv"
)
DEFAULT_UNIVERSE = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "shared_species_universe.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "species_name_resolution.csv"
)
DEFAULT_CACHE = (
    PROJECT_ROOT
    / "Data"
    / "processed"
    / "discovery"
    / "shared"
    / "cache"
    / "gbif_match_cache.csv"
)

FUZZY_CONFIDENCE_THRESHOLD = 90

# Intern repeated strings to save memory
_interned: dict[str, str] = {}


def _intern(s: str) -> str:
    if s not in _interned:
        _interned[s] = s
    return _interned[s]


# ── Backbone loading ────────────────────────────────────────────────


def load_backbone(
    zip_path: Path,
) -> tuple[dict[int, tuple], dict[str, list[int]]]:
    """Load Taxon.tsv → (by_taxonid, by_canonical).

    by_taxonid:  {taxonID_int: (canonicalName, acceptedID_int, status, kingdom, rank)}
    by_canonical: {lower(canonicalName): [taxonID_int, ...]}
    """
    by_taxonid: dict[int, tuple] = {}
    by_canonical: dict[str, list[int]] = defaultdict(list)

    print("Loading GBIF backbone Taxon.tsv ...", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("Taxon.tsv") as f:
            header = f.readline().decode("utf-8").strip().split("\t")
            idx = {col: i for i, col in enumerate(header)}
            i_tid = idx["taxonID"]
            i_cn = idx["canonicalName"]
            i_anui = idx["acceptedNameUsageID"]
            i_ts = idx["taxonomicStatus"]
            i_k = idx["kingdom"]
            i_rank = idx["taxonRank"]
            max_idx = max(i_tid, i_cn, i_anui, i_ts, i_k, i_rank)

            n = 0
            for line in f:
                n += 1
                fields = line.decode("utf-8", errors="replace").rstrip("\n\r").split("\t")
                if len(fields) <= max_idx:
                    fields.extend([""] * (max_idx + 1 - len(fields)))

                try:
                    tid = int(fields[i_tid])
                except ValueError:
                    continue
                cn = fields[i_cn].strip()
                anui_raw = fields[i_anui].strip()
                anui = int(anui_raw) if anui_raw else 0
                ts = _intern(fields[i_ts].strip().lower())
                kingdom = _intern(fields[i_k].strip())
                rank = _intern(fields[i_rank].strip().lower())

                by_taxonid[tid] = (cn, anui, ts, kingdom, rank)
                if cn:
                    by_canonical[cn.lower()].append(tid)

                if n % 2_000_000 == 0:
                    print(f"  {n:,} rows ...", flush=True)

    print(
        f"  done: {n:,} rows, {len(by_taxonid):,} taxa, "
        f"{len(by_canonical):,} unique canonical names",
        flush=True,
    )
    return by_taxonid, by_canonical


def resolve_to_accepted(
    tid: int,
    by_taxonid: dict[int, tuple],
    max_hops: int = 10,
) -> tuple[int, str, str] | None:
    """Follow synonym chain → (accepted_tid, accepted_canonicalName, accepted_kingdom)."""
    visited: set[int] = set()
    for _ in range(max_hops):
        if tid in visited or tid not in by_taxonid:
            return None
        visited.add(tid)
        cn, anui, ts, kingdom, _rank = by_taxonid[tid]
        if ts == "accepted" or anui == 0:
            return (tid, cn, kingdom)
        tid = anui
    return None


# ── LOTUS gbifid extraction ────────────────────────────────────────


def load_lotus_gbifids(meta_path: Path) -> dict[str, int]:
    """Build {lower(species_name): gbifid_int} from LOTUS metadata."""
    print("Loading LOTUS gbifids ...", flush=True)
    species_votes: dict[str, Counter] = defaultdict(Counter)
    n = 0
    with gzip.open(meta_path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n += 1
            sp = (row.get("organism_taxonomy_09species") or "").strip()
            gid_raw = (row.get("organism_taxonomy_gbifid") or "").strip()
            if sp and gid_raw:
                try:
                    gid = int(float(gid_raw))
                    species_votes[sp.lower()][gid] += 1
                except ValueError:
                    pass

    result: dict[str, int] = {}
    for sp, votes in species_votes.items():
        result[sp] = votes.most_common(1)[0][0]

    print(f"  {n:,} LOTUS rows scanned, {len(result):,} species with gbifid", flush=True)
    return result


# ── GBIF API match with disk cache ─────────────────────────────────


def load_api_cache(cache_path: Path) -> dict[str, dict]:
    """Load {input_name: {match_type, confidence, usage_key, ...}}."""
    cache: dict[str, dict] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cache[row["input_name"]] = row
    print(f"  loaded {len(cache):,} cached API results", flush=True)
    return cache


def save_api_cache(cache_path: Path, cache: dict[str, dict]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "input_name",
        "match_type",
        "confidence",
        "usage_key",
        "canonical_name",
        "kingdom",
        "status",
    ]
    with cache_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for name in sorted(cache):
            writer.writerow(cache[name])
    print(f"  saved {len(cache):,} entries to {cache_path}", flush=True)


GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"


def gbif_api_match(name: str, timeout: int = 30) -> dict:
    url = f"{GBIF_MATCH_URL}?name={urllib.parse.quote(name)}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Diversity_Discoveries/replication"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    parser.add_argument("--lotus-meta", type=Path, default=DEFAULT_LOTUS_META)
    parser.add_argument("--np-summary", type=Path, default=DEFAULT_NP)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip GBIF API fuzzy matching (steps 1-2 only).",
    )
    args = parser.parse_args()

    # ── Step 0: load backbone ───────────────────────────────────────
    by_taxonid, by_canonical = load_backbone(args.backbone)

    # ── Build genus → kingdom map (skip homonyms across kingdoms) ───
    # Side artifact for downstream kingdom backfill of genus-only / sp.
    # placeholder NP-DB names that fail species-level resolution.
    print("Building genus → kingdom map ...", flush=True)
    genus_kingdoms: dict[str, set[str]] = defaultdict(set)
    for _tid, (cn, _anui, ts, kingdom, rank) in by_taxonid.items():
        if rank == "genus" and ts == "accepted" and cn and kingdom:
            genus_kingdoms[cn.lower()].add(kingdom)
    genus_to_kingdom: dict[str, str] = {}
    n_homonym = 0
    for g, ks in genus_kingdoms.items():
        if len(ks) == 1:
            genus_to_kingdom[g] = next(iter(ks))
        else:
            n_homonym += 1
    print(
        f"  {len(genus_to_kingdom):,} genera mapped, "
        f"{n_homonym:,} skipped (cross-kingdom homonyms, e.g. Morus)",
        flush=True,
    )
    genus_map_path = args.output.parent / "genus_to_kingdom.csv"
    genus_map_path.parent.mkdir(parents=True, exist_ok=True)
    with genus_map_path.open("w", newline="", encoding="utf-8") as gf:
        gw = csv.DictWriter(gf, fieldnames=["genus_lower", "kingdom"])
        gw.writeheader()
        for g in sorted(genus_to_kingdom):
            gw.writerow({"genus_lower": g, "kingdom": genus_to_kingdom[g]})
    print(f"Wrote: {genus_map_path}", flush=True)

    # ── Load LOTUS gbifids ──────────────────────────────────────────
    lotus_gbifids = load_lotus_gbifids(args.lotus_meta)

    # ── Load input files ────────────────────────────────────────────
    print("\nLoading input files ...", flush=True)

    np_species: dict[str, dict] = {}
    with args.np_summary.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sp = row["species_name"].strip().lower()
            np_species[sp] = {
                "kingdom": row.get("kingdom", "").strip(),
                "sources": row.get("sources", "").strip(),
            }
    print(f"  NP-DB species: {len(np_species):,}", flush=True)

    uni_species: dict[str, dict] = {}
    with args.universe.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sp = row["species_name"].strip().lower()
            uni_species[sp] = {
                "kingdom": row.get("kingdom", "").strip(),
            }
    print(f"  Universe species: {len(uni_species):,}", flush=True)

    all_names: dict[str, dict] = {}
    for sp, info in np_species.items():
        all_names[sp] = {
            "input_source": "np_db",
            "kingdom_input": info["kingdom"],
            "has_lotus": "lotus" in info.get("sources", ""),
        }
    for sp, info in uni_species.items():
        if sp in all_names:
            all_names[sp]["input_source"] = "both"
            if not all_names[sp]["kingdom_input"]:
                all_names[sp]["kingdom_input"] = info["kingdom"]
        else:
            all_names[sp] = {
                "input_source": "shared_universe",
                "kingdom_input": info["kingdom"],
                "has_lotus": False,
            }

    print(f"  Total unique names: {len(all_names):,}", flush=True)
    n_both = sum(1 for v in all_names.values() if v["input_source"] == "both")
    print(f"  Appearing in both inputs: {n_both:,}", flush=True)

    # ── Resolution ──────────────────────────────────────────────────

    results: dict[str, dict] = {}

    # --- Step 1: gbifid_lookup (LOTUS species with gbifids) ---------
    print("\nStep 1: gbifid_lookup ...", flush=True)
    n_gbifid = 0
    for sp, info in all_names.items():
        if sp in lotus_gbifids:
            gid = lotus_gbifids[sp]
            if gid in by_taxonid:
                cn, anui, ts, kingdom, rank = by_taxonid[gid]
                accepted = resolve_to_accepted(gid, by_taxonid)
                if accepted:
                    a_tid, a_cn, a_kingdom = accepted
                    results[sp] = {
                        "resolved_name": a_cn.lower() if a_cn else "",
                        "resolved_taxon_id": a_tid,
                        "kingdom_resolved": a_kingdom,
                        "resolution_method": "gbifid_lookup",
                        "match_confidence": 100,
                        "taxonomic_status_input": ts,
                    }
                    n_gbifid += 1
    print(f"  resolved: {n_gbifid:,}", flush=True)

    # --- Step 2: name_match_exact ------------------------------------
    print("Step 2: name_match_exact ...", flush=True)
    n_exact = 0
    for sp, info in all_names.items():
        if sp in results:
            continue
        candidates = by_canonical.get(sp, [])
        if not candidates:
            continue

        accepted_candidates = []
        synonym_targets = []
        for tid in candidates:
            cn, anui, ts, kingdom, rank = by_taxonid[tid]
            if ts == "accepted":
                accepted_candidates.append((tid, cn, kingdom, ts))
            elif anui:
                target = resolve_to_accepted(anui, by_taxonid)
                if target:
                    synonym_targets.append((tid, ts, target))

        chosen = None
        chosen_status = ""

        if len(accepted_candidates) == 1:
            tid, cn, kingdom, ts = accepted_candidates[0]
            chosen = (tid, cn, kingdom)
            chosen_status = ts
        elif len(accepted_candidates) > 1:
            # homonym: disambiguate by kingdom
            k_input = info["kingdom_input"]
            if k_input:
                matches = [
                    (tid, cn, k, ts)
                    for tid, cn, k, ts in accepted_candidates
                    if k.lower() == k_input.lower()
                ]
                if len(matches) == 1:
                    tid, cn, kingdom, ts = matches[0]
                    chosen = (tid, cn, kingdom)
                    chosen_status = ts
        elif synonym_targets:
            # all candidates are synonyms — follow to accepted
            unique_accepted = {}
            for orig_tid, orig_ts, (a_tid, a_cn, a_kingdom) in synonym_targets:
                unique_accepted[a_tid] = (a_cn, a_kingdom, orig_ts)
            if len(unique_accepted) == 1:
                a_tid = next(iter(unique_accepted))
                a_cn, a_kingdom, orig_ts = unique_accepted[a_tid]
                chosen = (a_tid, a_cn, a_kingdom)
                chosen_status = orig_ts
            elif len(unique_accepted) > 1:
                k_input = info["kingdom_input"]
                if k_input:
                    matches = {
                        a_tid: (a_cn, a_k, ots)
                        for a_tid, (a_cn, a_k, ots) in unique_accepted.items()
                        if a_k.lower() == k_input.lower()
                    }
                    if len(matches) == 1:
                        a_tid = next(iter(matches))
                        a_cn, a_kingdom, orig_ts = matches[a_tid]
                        chosen = (a_tid, a_cn, a_kingdom)
                        chosen_status = orig_ts

        if chosen:
            a_tid, a_cn, a_kingdom = chosen
            results[sp] = {
                "resolved_name": a_cn.lower() if a_cn else "",
                "resolved_taxon_id": a_tid,
                "kingdom_resolved": a_kingdom,
                "resolution_method": "name_match_exact",
                "match_confidence": 100,
                "taxonomic_status_input": chosen_status,
            }
            n_exact += 1

    print(f"  resolved: {n_exact:,}", flush=True)

    # --- Step 3: name_match_fuzzy (API, NP-DB names only) -----------
    n_fuzzy = 0
    if not args.skip_api:
        unresolved_np = [
            sp
            for sp, info in all_names.items()
            if sp not in results and info["input_source"] in ("np_db", "both")
        ]
        print(
            f"Step 3: name_match_fuzzy — {len(unresolved_np):,} NP-DB names to query ...",
            flush=True,
        )

        cache = load_api_cache(args.cache)
        n_api_calls = 0
        n_cache_hits = 0
        n_api_errors = 0

        for i, sp in enumerate(unresolved_np):
            if sp in cache:
                api_result = cache[sp]
                n_cache_hits += 1
            else:
                try:
                    resp = gbif_api_match(sp)
                    api_result = {
                        "input_name": sp,
                        "match_type": resp.get("matchType", ""),
                        "confidence": str(resp.get("confidence", "")),
                        "usage_key": str(resp.get("usageKey", "")),
                        "canonical_name": resp.get("canonicalName", ""),
                        "kingdom": resp.get("kingdom", ""),
                        "status": resp.get("status", ""),
                    }
                    cache[sp] = api_result
                    n_api_calls += 1
                    if n_api_calls % 100 == 0:
                        time.sleep(0.5)
                    if n_api_calls % 500 == 0:
                        save_api_cache(args.cache, cache)
                except Exception as exc:
                    n_api_errors += 1
                    if n_api_errors <= 5:
                        print(f"  API error for '{sp}': {exc}", flush=True)
                    continue

            match_type = api_result.get("match_type", "")
            confidence_str = api_result.get("confidence", "")
            try:
                confidence = int(confidence_str)
            except (ValueError, TypeError):
                confidence = 0
            usage_key_str = api_result.get("usage_key", "")

            if match_type in ("EXACT", "FUZZY") and confidence >= FUZZY_CONFIDENCE_THRESHOLD:
                try:
                    usage_key = int(usage_key_str)
                except (ValueError, TypeError):
                    continue
                accepted = resolve_to_accepted(usage_key, by_taxonid)
                if accepted:
                    a_tid, a_cn, a_kingdom = accepted
                    ts_input = ""
                    if usage_key in by_taxonid:
                        ts_input = by_taxonid[usage_key][2]
                    results[sp] = {
                        "resolved_name": a_cn.lower() if a_cn else "",
                        "resolved_taxon_id": a_tid,
                        "kingdom_resolved": a_kingdom,
                        "resolution_method": "name_match_fuzzy",
                        "match_confidence": confidence,
                        "taxonomic_status_input": ts_input,
                    }
                    n_fuzzy += 1

            if (i + 1) % 1000 == 0:
                print(
                    f"  progress: {i+1:,}/{len(unresolved_np):,} "
                    f"(fuzzy resolved: {n_fuzzy:,}, "
                    f"API calls: {n_api_calls:,}, "
                    f"cache hits: {n_cache_hits:,})",
                    flush=True,
                )

        save_api_cache(args.cache, cache)
        print(
            f"  resolved: {n_fuzzy:,} "
            f"(API calls: {n_api_calls:,}, cache hits: {n_cache_hits:,}, "
            f"errors: {n_api_errors:,})",
            flush=True,
        )
    else:
        print("Step 3: skipped (--skip-api)", flush=True)

    # --- Step 4: mark unresolved ------------------------------------
    n_unresolved = 0
    for sp in all_names:
        if sp not in results:
            results[sp] = {
                "resolved_name": "",
                "resolved_taxon_id": "",
                "kingdom_resolved": "",
                "resolution_method": "unresolved",
                "match_confidence": "",
                "taxonomic_status_input": "",
            }
            n_unresolved += 1
    print(f"Step 4: unresolved: {n_unresolved:,}", flush=True)

    # ── Write output ────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_fields = [
        "input_name",
        "input_source",
        "resolved_name",
        "resolved_taxon_id",
        "kingdom_resolved",
        "resolution_method",
        "match_confidence",
        "taxonomic_status_input",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for sp in sorted(all_names.keys()):
            row = {"input_name": sp, "input_source": all_names[sp]["input_source"]}
            row.update(results[sp])
            writer.writerow(row)

    print(f"\nWrote: {args.output} ({len(results):,} rows)", flush=True)

    # ── Report ──────────────────────────────────────────────────────
    print("\n" + "=" * 70, flush=True)
    print("SPECIES NAME RESOLUTION — REPORT", flush=True)
    print("=" * 70, flush=True)

    total = len(results)
    method_counts: Counter = Counter()
    kingdom_method: dict[str, Counter] = defaultdict(Counter)
    n_synonym_redirect = 0

    for sp, res in results.items():
        method = res["resolution_method"]
        method_counts[method] += 1
        k = res["kingdom_resolved"] or all_names[sp]["kingdom_input"] or "(unknown)"
        kingdom_method[k][method] += 1
        if res["resolved_name"] and res["resolved_name"] != sp:
            n_synonym_redirect += 1

    print(f"\nTotal unique input names: {total:,}", flush=True)
    print(f"\nResolution method breakdown:", flush=True)
    for method in ["gbifid_lookup", "name_match_exact", "name_match_fuzzy", "unresolved"]:
        c = method_counts[method]
        pct = 100 * c / total if total else 0
        print(f"  {method:<22s} {c:>9,}  ({pct:.1f}%)", flush=True)

    print(f"\nSynonym redirects (resolved_name != input_name): {n_synonym_redirect:,}", flush=True)

    print(f"\nPer-kingdom breakdown:", flush=True)
    for k in sorted(kingdom_method.keys()):
        counts = kingdom_method[k]
        k_total = sum(counts.values())
        resolved = k_total - counts.get("unresolved", 0)
        print(f"  {k:<20s}  total={k_total:>8,}  resolved={resolved:>8,}  ({100*resolved/k_total:.1f}%)", flush=True)

    # ── Estimated join improvement ──────────────────────────────────
    # Correct metric: count NP input species whose resolved_name
    # appears in the set of resolved universe names.
    print(f"\nEstimated species→compound join improvement:", flush=True)

    uni_resolved_names: set[str] = set()
    for sp in uni_species:
        r = results.get(sp, {})
        rn = r.get("resolved_name", "")
        uni_resolved_names.add(rn if rn else sp)

    baseline_count = 0
    new_count = 0
    newly_matched: list[tuple[str, str]] = []
    for sp, info in np_species.items():
        in_uni_raw = sp in uni_species
        if in_uni_raw:
            baseline_count += 1
        r = results.get(sp, {})
        rn = r.get("resolved_name", "")
        resolved = rn if rn else sp
        if resolved in uni_resolved_names:
            new_count += 1
            if not in_uni_raw:
                k = info.get("kingdom", "") or r.get("kingdom_resolved", "") or "(unknown)"
                newly_matched.append((sp, k))

    n_np = len(np_species)
    print(f"  NP species total:                       {n_np:>8,}", flush=True)
    print(
        f"  Baseline (raw name in universe):        {baseline_count:>8,}"
        f"  ({100*baseline_count/n_np:.1f}%)",
        flush=True,
    )
    print(
        f"  After resolution (resolved name match): {new_count:>8,}"
        f"  ({100*new_count/n_np:.1f}%)",
        flush=True,
    )
    print(
        f"  Gain:                                   {new_count - baseline_count:>+8,}"
        f"  ({100*(new_count - baseline_count)/n_np:+.1f}pp)",
        flush=True,
    )

    if newly_matched:
        new_kingdom: Counter = Counter()
        for _sp, k in newly_matched:
            new_kingdom[k] += 1
        print(f"\n  Newly matched NP species by kingdom:", flush=True)
        for k, c in new_kingdom.most_common():
            print(f"    {k:<20s} {c:>7,}", flush=True)

    print("=" * 70, flush=True)

    # ── Finalize NP-DB kingdoms ─────────────────────────────────────
    # Overwrites Script 23's initial outputs with kingdom-backfilled
    # versions. Two-pass backfill on species_compound_pairs.csv:
    #   1. species-level via results[sp].kingdom_resolved (GBIF backbone)
    #   2. genus-level via genus_to_kingdom (skips cross-kingdom homonyms)
    # Then per-species summary is rebuilt from the patched pairs.
    print("\nFinalizing NP-DB kingdoms ...", flush=True)
    import pandas as pd

    pairs_path = args.np_summary.parent / "species_compound_pairs.csv"
    pairs = pd.read_csv(pairs_path, dtype=str).fillna("")

    # species-level map: input_name (lowercase) → kingdom_resolved
    sp_kingdom = {
        sp: r["kingdom_resolved"]
        for sp, r in results.items()
        if r.get("kingdom_resolved")
    }

    missing0 = (pairs["kingdom"] == "").sum()
    pairs_lower = pairs["species_name"].str.lower()
    fill_sp = (pairs["kingdom"] == "") & pairs_lower.isin(sp_kingdom)
    pairs.loc[fill_sp, "kingdom"] = pairs_lower[fill_sp].map(sp_kingdom)
    missing1 = (pairs["kingdom"] == "").sum()

    pairs_genus_lower = pairs["genus"].str.lower().str.strip()
    fill_g = (pairs["kingdom"] == "") & pairs_genus_lower.isin(genus_to_kingdom)
    pairs.loc[fill_g, "kingdom"] = pairs_genus_lower[fill_g].map(genus_to_kingdom)
    missing2 = (pairs["kingdom"] == "").sum()

    print(
        f"  pair rows w/ empty kingdom: {missing0:,} → {missing1:,} (species pass) "
        f"→ {missing2:,} (genus pass; remainder: placeholder/unknown/homonym)",
        flush=True,
    )

    pairs.to_csv(pairs_path, index=False)
    print(f"  Re-wrote: {pairs_path}", flush=True)

    # Rebuild per-species summary from patched pairs.
    def _agg_species(g):
        return pd.Series(
            {
                "genus": g["genus"].iloc[0],
                "kingdom": (
                    g["kingdom"].loc[g["kingdom"] != ""].iloc[0]
                    if (g["kingdom"] != "").any()
                    else ""
                ),
                "n_compounds_lotus": g.loc[
                    g["source_set"].str.contains("lotus"), "inchikey"
                ].nunique(),
                "n_compounds_coconut": g.loc[
                    g["source_set"].str.contains("coconut"), "inchikey"
                ].nunique(),
                "n_unique_compounds_total": g["inchikey"].nunique(),
                "sources": ",".join(
                    sorted({s for ss in g["source_set"] for s in ss.split(",")})
                ),
            }
        )

    summary = (
        pairs.groupby(pairs["species_name"].str.lower(), sort=False)
        .apply(_agg_species, include_groups=False)
        .reset_index()
    )
    summary.rename(columns={"species_name": "species_name_lower"}, inplace=True)
    display = (
        pairs[["species_name"]]
        .assign(species_lower=pairs["species_name"].str.lower())
        .drop_duplicates(subset="species_lower")
        .set_index("species_lower")["species_name"]
    )
    summary["species_name"] = summary["species_name_lower"].map(display)
    summary = summary[
        [
            "species_name",
            "genus",
            "kingdom",
            "n_compounds_lotus",
            "n_compounds_coconut",
            "n_unique_compounds_total",
            "sources",
        ]
    ].sort_values("n_unique_compounds_total", ascending=False)

    summary.to_csv(args.np_summary, index=False)
    print(
        f"  Re-wrote: {args.np_summary} ({len(summary):,} rows; "
        f"kingdom unknown: {(summary['kingdom']=='').sum():,})",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
