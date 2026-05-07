#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(BIEN)
  library(readr)
  library(dplyr)
  library(stringr)
  library(tibble)
  library(purrr)
})

PROJECT_ROOT <- "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
DEFAULT_UNIVERSE_CSV <- file.path(
  PROJECT_ROOT,
  "Data",
  "regressors",
  "plants",
  "gbif_plantae_species_universe_1999_2025.csv"
)
DEFAULT_BATCH_ID <- 1L
DEFAULT_RANK_START <- 1L
DEFAULT_TOP_N <- 5000L

default_outdir <- function(batch_id, rank_start, top_n) {
  rank_end <- rank_start + top_n - 1L
  file.path(
    PROJECT_ROOT,
    "Data",
    "raw",
    "bien",
    "batches",
    sprintf("batch_%03d_ranks_%06d_%06d", batch_id, rank_start, rank_end)
  )
}

usage <- function() {
  cat(
    paste(
      "Usage:",
      "  Rscript Scripts/18_bien_range_download_pilot.R [options]",
      "",
      "Default behavior:",
      "  - read the GBIF plant species universe CSV",
      "  - keep ranks 1-5000 by total_records (batch 1)",
      "  - check BIEN range availability",
      "  - download available BIEN range shapefiles into a fresh local directory",
      "",
      "Options:",
      "  --species-universe-csv PATH   Ranked GBIF species universe CSV.",
      "  --batch-id N                  Batch label used in the default output path (default 1).",
      "  --rank-start N                1-indexed start rank in the canonical species pool (default 1).",
      "  --top-n N                     Number of ranked species in this batch (default 5000).",
      "  --availability-batch-size N   Batch size for BIEN availability queries (default 250).",
      "  --outdir PATH                 Output directory for BIEN download and manifests.",
      "  --batch-size N                Batch size passed to BIEN_ranges_species_bulk().",
      "  --template-raster PATH        Optional raster template for skinny/richness build.",
      "  --skinny-rds PATH             Optional output RDS for skinny ranges.",
      "  --richness-raster PATH        Optional output raster path for richness raster.",
      "  --notify-email EMAIL          Optional completion email via Apple Mail on macOS.",
      "  --use-parallel                Ask BIEN bulk downloader to parallelize batches.",
      "  --availability-only           Check BIEN range availability, do not download files.",
      "  --overwrite                   Allow reuse of an existing outdir.",
      "  --help                        Show this message.",
      sep = "\n"
    )
  )
}

parse_args <- function(args) {
  out <- list(
    species_universe_csv = DEFAULT_UNIVERSE_CSV,
    batch_id = DEFAULT_BATCH_ID,
    rank_start = DEFAULT_RANK_START,
    top_n = DEFAULT_TOP_N,
    availability_batch_size = 250L,
    outdir = default_outdir(DEFAULT_BATCH_ID, DEFAULT_RANK_START, DEFAULT_TOP_N),
    batch_size = 25L,
    template_raster = NULL,
    skinny_rds = NULL,
    richness_raster = NULL,
    notify_email = NULL,
    use_parallel = FALSE,
    availability_only = FALSE,
    overwrite = FALSE,
    help = FALSE
  )

  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key == "--use-parallel") {
      out$use_parallel <- TRUE
      i <- i + 1L
      next
    }
    if (key == "--availability-only") {
      out$availability_only <- TRUE
      i <- i + 1L
      next
    }
    if (key == "--overwrite") {
      out$overwrite <- TRUE
      i <- i + 1L
      next
    }
    if (key == "--help") {
      out$help <- TRUE
      i <- i + 1L
      next
    }
    if (i == length(args)) {
      stop("Missing value for argument: ", key, call. = FALSE)
    }
    value <- args[[i + 1L]]
    if (key == "--species-universe-csv") out$species_universe_csv <- value
    else if (key == "--batch-id") out$batch_id <- as.integer(value)
    else if (key == "--rank-start") out$rank_start <- as.integer(value)
    else if (key == "--top-n") out$top_n <- as.integer(value)
    else if (key == "--availability-batch-size") out$availability_batch_size <- as.integer(value)
    else if (key == "--outdir") out$outdir <- value
    else if (key == "--batch-size") out$batch_size <- as.integer(value)
    else if (key == "--template-raster") out$template_raster <- value
    else if (key == "--skinny-rds") out$skinny_rds <- value
    else if (key == "--richness-raster") out$richness_raster <- value
    else if (key == "--notify-email") out$notify_email <- value
    else stop("Unknown argument: ", key, call. = FALSE)
    i <- i + 2L
  }

  out
}

normalize_species <- function(x) {
  x <- str_replace_all(x, "_", " ")
  x <- str_squish(x)
  x[nzchar(x)]
}

canonical_binomial <- function(x) {
  x <- normalize_species(x)
  if (length(x) == 0L) {
    return(character())
  }

  out <- rep("", length(x))
  rank_markers <- c("subsp.", "subsp", "ssp.", "ssp", "var.", "var", "subvar.", "f.", "forma")

  for (i in seq_along(x)) {
    s <- x[[i]]
    toks <- unlist(strsplit(s, "\\s+"))
    if (length(toks) < 2L) {
      next
    }
    genus <- toks[[1L]]
    epithet <- toks[[2L]]
    if (!grepl("^[A-Z][[:alpha:]-]+$", genus)) {
      next
    }
    if (tolower(epithet) %in% rank_markers) {
      next
    }
    if (!grepl("^[a-z][[:alpha:]-]+$", epithet)) {
      next
    }
    out[[i]] <- paste(genus, epithet)
  }

  out
}

snake_names <- function(x) {
  x <- gsub("[?]", "", x)
  x <- gsub("[^A-Za-z0-9]+", "_", x)
  x <- gsub("(^_+|_+$)", "", x)
  tolower(x)
}

file_manifest <- function(path) {
  files <- list.files(path, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE)
  if (length(files) == 0L) {
    return(tibble(
      relative_path = character(),
      extension = character(),
      size_bytes = numeric()
    ))
  }
  tibble(
    relative_path = substring(files, nchar(normalizePath(path, winslash = "/", mustWork = FALSE)) + 2L),
    extension = tolower(tools::file_ext(files)),
    size_bytes = file.info(files)$size
  )
}

find_downloaded_species <- function(download_dir) {
  shp <- list.files(download_dir, pattern = "\\.shp$", recursive = TRUE, full.names = FALSE)
  if (length(shp) == 0L) {
    return(tibble(species_normalized = character(), shp_relative_path = character()))
  }
  tibble(
    species_normalized = normalize_species(tools::file_path_sans_ext(basename(shp))),
    shp_relative_path = shp
  ) |>
    distinct()
}

assert_fresh_outdir <- function(outdir, overwrite) {
  if (!dir.exists(outdir)) {
    return(invisible(TRUE))
  }
  existing <- list.files(outdir, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE)
  if (length(existing) == 0L || overwrite) {
    return(invisible(TRUE))
  }
  stop(
    paste0(
      "Output directory already contains files: ", outdir, "\n",
      "Use a fresh --outdir or pass --overwrite if you intentionally want to reuse it."
    ),
    call. = FALSE
  )
}

send_mail_macos <- function(to_email, subject, body) {
  if (is.null(to_email) || !nzchar(to_email)) {
    return(invisible(FALSE))
  }
  if (Sys.info()[["sysname"]] != "Darwin") {
    warning("Email notification is only implemented for macOS Mail.", call. = FALSE)
    return(invisible(FALSE))
  }

  esc <- function(x) {
    x <- gsub("\\\\", "\\\\\\\\", x)
    x <- gsub("\"", "\\\\\"", x)
    x
  }

  script_lines <- c(
    'tell application "Mail"',
    sprintf('set newMessage to make new outgoing message with properties {subject:"%s", content:"%s", visible:false}', esc(subject), esc(body)),
    'tell newMessage',
    sprintf('make new to recipient at end of to recipients with properties {address:"%s"}', esc(to_email)),
    "send",
    "end tell",
    "end tell"
  )

  script_path <- tempfile("bien_mail_", fileext = ".applescript")
  writeLines(script_lines, script_path, useBytes = TRUE)
  on.exit(unlink(script_path), add = TRUE)

  status <- tryCatch(
    system2("osascript", args = script_path, stdout = TRUE, stderr = TRUE),
    error = function(e) e
  )
  if (inherits(status, "error")) {
    warning("Failed to send Mail notification: ", conditionMessage(status), call. = FALSE)
    return(invisible(FALSE))
  }
  invisible(TRUE)
}

availability_query_once <- function(species_vec) {
  result <- tryCatch(
    BIEN::BIEN_ranges_species(
      species = species_vec,
      match_names_only = TRUE,
      matched = TRUE
    ),
    error = function(e) e
  )

  if (inherits(result, "error") || is.null(result)) {
    return(NULL)
  }

  names(result) <- snake_names(names(result))
  if (!all(c("species", "range_map_available") %in% names(result))) {
    return(NULL)
  }

  as_tibble(result) |>
    mutate(
      species_normalized = normalize_species(species),
      range_map_available = ifelse(range_map_available == "Yes", TRUE, FALSE),
      query_status = "ok"
    ) |>
    select(species_normalized, range_map_available, query_status)
}

availability_query_recursive <- function(species_vec) {
  if (length(species_vec) == 0L) {
    return(tibble(
      species_normalized = character(),
      range_map_available = logical(),
      query_status = character()
    ))
  }

  res <- availability_query_once(species_vec)
  if (!is.null(res)) {
    return(res)
  }

  if (length(species_vec) == 1L) {
    return(tibble(
      species_normalized = species_vec,
      range_map_available = FALSE,
      query_status = "query_error"
    ))
  }

  mid <- floor(length(species_vec) / 2L)
  bind_rows(
    availability_query_recursive(species_vec[seq_len(mid)]),
    availability_query_recursive(species_vec[(mid + 1L):length(species_vec)])
  )
}

run_batched_availability <- function(species_vec, batch_size) {
  batches <- split(species_vec, ceiling(seq_along(species_vec) / batch_size))
  pieces <- vector("list", length(batches))
  for (i in seq_along(batches)) {
    message("Availability batch ", i, " of ", length(batches), " (", length(batches[[i]]), " species)")
    pieces[[i]] <- availability_query_recursive(batches[[i]])
  }
  bind_rows(pieces)
}

main <- function() {
  opts <- parse_args(commandArgs(trailingOnly = TRUE))
  if (opts$help) {
    usage()
    return(invisible(0L))
  }

  if (!file.exists(opts$species_universe_csv)) {
    stop("Missing species universe CSV: ", opts$species_universe_csv, call. = FALSE)
  }
  if (!is.finite(opts$batch_id) || opts$batch_id <= 0) {
    stop("--batch-id must be a positive integer", call. = FALSE)
  }
  if (!is.finite(opts$rank_start) || opts$rank_start <= 0) {
    stop("--rank-start must be a positive integer", call. = FALSE)
  }
  if (!is.finite(opts$top_n) || opts$top_n <= 0) {
    stop("--top-n must be a positive integer", call. = FALSE)
  }
  if (!is.finite(opts$availability_batch_size) || opts$availability_batch_size <= 0) {
    stop("--availability-batch-size must be a positive integer", call. = FALSE)
  }

  assert_fresh_outdir(opts$outdir, opts$overwrite)

  dir.create(opts$outdir, recursive = TRUE, showWarnings = FALSE)
  download_dir <- file.path(opts$outdir, "downloads")
  dir.create(download_dir, recursive = TRUE, showWarnings = FALSE)
  manifest_dir <- file.path(opts$outdir, "manifests")
  dir.create(manifest_dir, recursive = TRUE, showWarnings = FALSE)

  universe <- readr::read_csv(opts$species_universe_csv, show_col_types = FALSE, progress = FALSE)
  required_cols <- c("species_name", "total_records")
  missing <- setdiff(required_cols, names(universe))
  if (length(missing) > 0L) {
    stop("Species universe CSV missing columns: ", paste(missing, collapse = ", "), call. = FALSE)
  }

  selected <- universe |>
    mutate(
      species_name = normalize_species(species_name),
      bien_query_name = canonical_binomial(species_name)
    ) |>
    filter(nzchar(bien_query_name)) |>
    group_by(bien_query_name) |>
    summarise(
      total_records = sum(total_records, na.rm = TRUE),
      source_variants = n(),
      representative_name = first(species_name),
      .groups = "drop"
    ) |>
    arrange(desc(total_records), bien_query_name) |>
    mutate(canonical_rank = row_number()) |>
    filter(canonical_rank >= opts$rank_start, canonical_rank < opts$rank_start + opts$top_n) |>
    mutate(species_bien_key = gsub(" ", "_", bien_query_name))

  rank_end <- if (nrow(selected) == 0L) opts$rank_start - 1L else max(selected$canonical_rank)

  requested_path <- file.path(manifest_dir, "requested_species.csv")
  availability_path <- file.path(manifest_dir, "availability.csv")
  downloaded_path <- file.path(manifest_dir, "downloaded_layers.csv")
  file_manifest_path <- file.path(manifest_dir, "file_manifest.csv")
  summary_path <- file.path(manifest_dir, "summary.csv")

  readr::write_csv(selected, requested_path)

  message(
    "Checking BIEN range availability for batch ", opts$batch_id,
    " (ranks ", opts$rank_start, "-", rank_end, ", n=", nrow(selected), ")"
  )
  t0 <- Sys.time()
  availability_raw <- run_batched_availability(selected$bien_query_name, opts$availability_batch_size)
  availability_seconds <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

  availability_full <- selected |>
    mutate(species_normalized = normalize_species(bien_query_name)) |>
    left_join(availability_raw, by = "species_normalized") |>
    mutate(
      range_map_available = ifelse(is.na(range_map_available), FALSE, range_map_available),
      query_status = ifelse(is.na(query_status), "unmatched", query_status)
    )
  readr::write_csv(availability_full, availability_path)

  available_species <- availability_full$bien_query_name[availability_full$range_map_available]
  download_seconds <- 0
  if (!opts$availability_only && length(available_species) > 0L) {
    message("Downloading BIEN range maps for ", length(available_species), " available species")
    t1 <- Sys.time()
    BIEN::BIEN_ranges_species_bulk(
      species = available_species,
      directory = download_dir,
      batch_size = opts$batch_size,
      return_directory = TRUE,
      use_parallel = opts$use_parallel
    )
    download_seconds <- as.numeric(difftime(Sys.time(), t1, units = "secs"))
  }

  downloaded_layers <- find_downloaded_species(download_dir)
  readr::write_csv(downloaded_layers, downloaded_path)

  manifest <- file_manifest(opts$outdir)
  readr::write_csv(manifest, file_manifest_path)

  total_bytes <- sum(manifest$size_bytes, na.rm = TRUE)
  shp_bytes <- sum(manifest$size_bytes[manifest$extension == "shp"], na.rm = TRUE)
  dbf_bytes <- sum(manifest$size_bytes[manifest$extension == "dbf"], na.rm = TRUE)
  prj_bytes <- sum(manifest$size_bytes[manifest$extension == "prj"], na.rm = TRUE)
  shx_bytes <- sum(manifest$size_bytes[manifest$extension == "shx"], na.rm = TRUE)

  summary <- tibble(
    metric = c(
      "species_universe_csv",
      "batch_id",
      "species_like_pool",
      "rank_start",
      "rank_end",
      "top_n_requested",
      "available_species",
      "availability_share",
      "query_errors",
      "download_attempted",
      "downloaded_unique_species",
      "downloaded_shapefiles",
      "availability_seconds",
      "download_seconds",
      "total_bytes",
      "shp_bytes",
      "dbf_bytes",
      "prj_bytes",
      "shx_bytes"
    ),
    value = c(
      opts$species_universe_csv,
      opts$batch_id,
      nrow(universe |>
        mutate(bien_query_name = canonical_binomial(species_name)) |>
        filter(nzchar(bien_query_name)) |>
        distinct(bien_query_name)),
      opts$rank_start,
      rank_end,
      nrow(selected),
      length(available_species),
      if (nrow(selected) > 0) length(available_species) / nrow(selected) else 0,
      sum(availability_full$query_status == "query_error"),
      as.integer(!opts$availability_only),
      dplyr::n_distinct(downloaded_layers$species_normalized),
      sum(manifest$extension == "shp"),
      availability_seconds,
      download_seconds,
      total_bytes,
      shp_bytes,
      dbf_bytes,
      prj_bytes,
      shx_bytes
    )
  )

  if (!is.null(opts$template_raster) && nrow(downloaded_layers) > 0L) {
    skinny_rds <- if (!is.null(opts$skinny_rds)) opts$skinny_rds else file.path(manifest_dir, "skinny_ranges.rds")
    richness_raster <- if (!is.null(opts$richness_raster)) opts$richness_raster else file.path(manifest_dir, "bien_richness.tif")
    tmpl <- terra::rast(opts$template_raster)
    t2 <- Sys.time()
    skinny <- BIEN::BIEN_ranges_shapefile_to_skinny(
      directory = download_dir,
      raster = opts$template_raster,
      skinny_ranges_file = skinny_rds
    )
    rich <- BIEN::BIEN_ranges_skinny_ranges_to_richness_raster(
      skinny_ranges = skinny,
      raster = tmpl
    )
    terra::writeRaster(rich, richness_raster, overwrite = opts$overwrite)
    conversion_seconds <- as.numeric(difftime(Sys.time(), t2, units = "secs"))
    summary <- bind_rows(
      summary,
      tibble(
        metric = c("skinny_ranges_rows", "richness_raster_written", "conversion_seconds"),
        value = c(nrow(skinny), as.integer(file.exists(richness_raster)), conversion_seconds)
      )
    )
  }

  readr::write_csv(summary, summary_path)

  message("Wrote requested species: ", requested_path)
  message("Wrote availability manifest: ", availability_path)
  message("Wrote downloaded layers manifest: ", downloaded_path)
  message("Wrote file manifest: ", file_manifest_path)
  message("Wrote summary: ", summary_path)

  if (!is.null(opts$notify_email) && nzchar(opts$notify_email)) {
    subject <- sprintf(
      "BIEN batch %03d finished: ranks %d-%d",
      opts$batch_id,
      opts$rank_start,
      rank_end
    )
    body <- paste(
      sprintf("BIEN batch %03d completed.", opts$batch_id),
      sprintf("Ranks: %d-%d", opts$rank_start, rank_end),
      sprintf("Requested species: %d", nrow(selected)),
      sprintf("Available species: %d", length(available_species)),
      sprintf("Downloaded species: %d", dplyr::n_distinct(downloaded_layers$species_normalized)),
      sprintf("Availability seconds: %.1f", availability_seconds),
      sprintf("Download seconds: %.1f", download_seconds),
      sprintf("Output directory: %s", normalizePath(opts$outdir, winslash = "/", mustWork = FALSE)),
      sprintf("Summary file: %s", normalizePath(summary_path, winslash = "/", mustWork = FALSE)),
      sep = "\n"
    )
    send_mail_macos(opts$notify_email, subject, body)
  }
}

main()
