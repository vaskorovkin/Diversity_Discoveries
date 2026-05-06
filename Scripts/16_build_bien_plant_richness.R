#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(BIEN)
  library(dplyr)
  library(readr)
  library(tibble)
})

PROJECT_ROOT <- "/Users/vasilykorovkin/Documents/Diversity_Discoveries"
DEFAULT_GRID <- file.path(PROJECT_ROOT, "Data", "processed", "bold", "bold_grid100_land_cells.geojson")
DEFAULT_OUTPUT <- file.path(PROJECT_ROOT, "Data", "regressors", "plants", "bien_plant_richness_100km_cells.csv")
DEFAULT_SUMMARY <- file.path(PROJECT_ROOT, "Data", "regressors", "plants", "bien_plant_richness_100km_cells_summary.csv")
DEFAULT_RESUME_DIR <- file.path(PROJECT_ROOT, "Output", "tmp", "bien_plant_richness_100km")

parse_args <- function(args) {
  out <- list(
    grid = DEFAULT_GRID,
    output = DEFAULT_OUTPUT,
    summary = DEFAULT_SUMMARY,
    resume_dir = DEFAULT_RESUME_DIR,
    chunk_size = 50L,
    start_index = 1L,
    end_index = NA_integer_,
    sleep_seconds = 0,
    overwrite = FALSE,
    finalize_only = FALSE,
    cultivated = FALSE
  )

  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key == "--overwrite") {
      out$overwrite <- TRUE
      i <- i + 1L
      next
    }
    if (key == "--finalize-only") {
      out$finalize_only <- TRUE
      i <- i + 1L
      next
    }
    if (key == "--cultivated") {
      out$cultivated <- TRUE
      i <- i + 1L
      next
    }
    if (i == length(args)) {
      stop("Missing value for argument: ", key, call. = FALSE)
    }
    value <- args[[i + 1L]]
    if (key == "--grid") out$grid <- value
    else if (key == "--output") out$output <- value
    else if (key == "--summary") out$summary <- value
    else if (key == "--resume-dir") out$resume_dir <- value
    else if (key == "--chunk-size") out$chunk_size <- as.integer(value)
    else if (key == "--start-index") out$start_index <- as.integer(value)
    else if (key == "--end-index") out$end_index <- as.integer(value)
    else if (key == "--sleep-seconds") out$sleep_seconds <- as.numeric(value)
    else stop("Unknown argument: ", key, call. = FALSE)
    i <- i + 2L
  }

  out
}

species_column <- function(df) {
  candidates <- c(
    "scrubbed_species_binomial",
    "species_binomial",
    "scrubbed_species",
    "species"
  )
  found <- candidates[candidates %in% names(df)]
  if (length(found) == 0L) {
    return(NA_character_)
  }
  found[[1L]]
}

count_species <- function(df, col) {
  values <- trimws(as.character(df[[col]]))
  values <- values[!is.na(values) & nzchar(values)]
  dplyr::n_distinct(values)
}

chunk_path <- function(resume_dir, start_idx, end_idx) {
  file.path(resume_dir, sprintf("chunk_%05d_%05d.csv", start_idx, end_idx))
}

combine_chunks <- function(resume_dir, output_path, summary_path, total_cells) {
  files <- sort(list.files(resume_dir, pattern = "^chunk_[0-9]{5}_[0-9]{5}\\.csv$", full.names = TRUE))
  if (length(files) == 0L) {
    message("No chunk files found in ", resume_dir)
    return(invisible(FALSE))
  }

  combined <- bind_rows(lapply(files, readr::read_csv, show_col_types = FALSE), .id = "chunk_source") |>
    group_by(cell_id) |>
    slice_tail(n = 1L) |>
    ungroup() |>
    select(-chunk_source)

  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(combined, output_path)

  summary <- tibble(
    metric = c(
      "chunk_files",
      "processed_cells",
      "total_grid_cells",
      "cells_with_success",
      "cells_with_error",
      "cells_with_zero_species",
      "mean_richness_success",
      "median_richness_success",
      "max_richness_success"
    ),
    value = c(
      length(files),
      nrow(combined),
      total_cells,
      sum(combined$status == "ok", na.rm = TRUE),
      sum(combined$status == "error", na.rm = TRUE),
      sum(combined$status == "ok" & combined$bien_species_richness == 0, na.rm = TRUE),
      mean(combined$bien_species_richness[combined$status == "ok"], na.rm = TRUE),
      stats::median(combined$bien_species_richness[combined$status == "ok"], na.rm = TRUE),
      max(combined$bien_species_richness[combined$status == "ok"], na.rm = TRUE)
    )
  )
  readr::write_csv(summary, summary_path)

  message("Wrote BIEN richness CSV: ", output_path)
  message("Wrote BIEN richness summary: ", summary_path)
  invisible(TRUE)
}

run_one_cell <- function(cell_row, cultivated) {
  started <- Sys.time()
  result <- tryCatch(
    BIEN::BIEN_list_sf(sf = cell_row, cultivated = cultivated),
    error = function(e) e
  )
  elapsed <- as.numeric(difftime(Sys.time(), started, units = "secs"))

  if (inherits(result, "error")) {
    return(tibble(
      cell_id = as.character(cell_row$cell_id[[1L]]),
      bien_species_richness = NA_integer_,
      bien_rows_returned = NA_integer_,
      bien_species_column = NA_character_,
      status = "error",
      error_message = substr(conditionMessage(result), 1L, 500L),
      query_seconds = elapsed
    ))
  }

  sp_col <- species_column(result)
  richness <- if (is.na(sp_col)) NA_integer_ else count_species(result, sp_col)

  tibble(
    cell_id = as.character(cell_row$cell_id[[1L]]),
    bien_species_richness = richness,
    bien_rows_returned = nrow(result),
    bien_species_column = sp_col,
    status = "ok",
    error_message = "",
    query_seconds = elapsed
  )
}

main <- function() {
  opts <- parse_args(commandArgs(trailingOnly = TRUE))

  dir.create(opts$resume_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(opts$output), recursive = TRUE, showWarnings = FALSE)

  grid <- st_read(opts$grid, quiet = TRUE)
  if (!"cell_id" %in% names(grid)) {
    stop("Grid file is missing required column: cell_id", call. = FALSE)
  }
  grid <- st_transform(grid, 4326)

  total_cells <- nrow(grid)
  end_index <- if (is.na(opts$end_index)) total_cells else min(opts$end_index, total_cells)
  start_index <- max(1L, opts$start_index)

  if (opts$finalize_only) {
    combine_chunks(opts$resume_dir, opts$output, opts$summary, total_cells)
    return(invisible(0L))
  }

  if (start_index > end_index) {
    stop("start-index exceeds end-index", call. = FALSE)
  }

  message("Reading grid: ", opts$grid)
  message("Total grid cells: ", format(total_cells, big.mark = ","))
  message("Processing cells ", start_index, " to ", end_index, " in chunks of ", opts$chunk_size)
  message("Chunk files: ", opts$resume_dir)

  chunk_starts <- seq.int(start_index, end_index, by = opts$chunk_size)
  processed_so_far <- 0L

  for (chunk_start in chunk_starts) {
    chunk_end <- min(chunk_start + opts$chunk_size - 1L, end_index)
    out_path <- chunk_path(opts$resume_dir, chunk_start, chunk_end)

    if (file.exists(out_path) && !opts$overwrite) {
      processed_so_far <- processed_so_far + (chunk_end - chunk_start + 1L)
      message("[skip] ", basename(out_path))
      next
    }

    chunk_grid <- grid[chunk_start:chunk_end, c("cell_id", "geometry")]
    rows <- vector("list", length = nrow(chunk_grid))

    for (j in seq_len(nrow(chunk_grid))) {
      global_idx <- chunk_start + j - 1L
      cell_row <- chunk_grid[j, ]
      cell_id <- as.character(cell_row$cell_id[[1L]])
      rows[[j]] <- run_one_cell(cell_row, cultivated = opts$cultivated)
      result <- rows[[j]]
      richness <- result$bien_species_richness[[1L]]
      status <- result$status[[1L]]
      msg <- if (status == "ok") {
        paste0("richness=", ifelse(is.na(richness), "NA", richness))
      } else {
        paste0("error=", result$error_message[[1L]])
      }
      message(
        "  [", global_idx, "/", end_index, "] ",
        cell_id, " ", msg,
        " (", sprintf("%.1fs", result$query_seconds[[1L]]), ")"
      )
      if (opts$sleep_seconds > 0 && global_idx < end_index) {
        Sys.sleep(opts$sleep_seconds)
      }
    }

    chunk_df <- bind_rows(rows)
    readr::write_csv(chunk_df, out_path)
    processed_so_far <- processed_so_far + nrow(chunk_df)
    message(
      "[wrote] ", out_path,
      " | progress ", format(processed_so_far, big.mark = ","), "/",
      format(end_index - start_index + 1L, big.mark = ","),
      " cells in requested range"
    )
  }

  combine_chunks(opts$resume_dir, opts$output, opts$summary, total_cells)
  invisible(0L)
}

main()
