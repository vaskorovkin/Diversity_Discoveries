#!/usr/bin/env Rscript

# Bootstrap an R environment for plant-richness work.
# This is intentionally light: it installs and loads the packages used for
# BIEN and WCVP/POWO-style workflows, then writes a small manifest.

args <- commandArgs(trailingOnly = TRUE)
install_pkgs <- "--install" %in% args

cran_repos <- c(CRAN = "https://cloud.r-project.org")
drat_repos <- c(rWCVPdata = "https://matildabrown.github.io/drat")
github_fallbacks <- list(
  BIEN = "bmaitner/RBIEN",
  rWCVP = "matildabrown/rWCVP",
  expowo = "dboslab/expowo"
)

required <- c(
  "BIEN",
  "rWCVP",
  "rWCVPdata",
  "expowo",
  "sf",
  "terra",
  "dplyr",
  "readr",
  "stringr",
  "tibble"
)

install_one <- function(pkg) {
  if (pkg == "rWCVPdata") {
    install.packages(pkg, repos = drat_repos, quiet = TRUE)
    return(invisible(TRUE))
  }
  ok <- tryCatch({
    install.packages(pkg, repos = cran_repos, quiet = TRUE)
    requireNamespace(pkg, quietly = TRUE)
  }, error = function(e) FALSE)
  if (ok) {
    return(invisible(TRUE))
  }
  if (pkg %in% names(github_fallbacks)) {
    if (!requireNamespace("remotes", quietly = TRUE)) {
      install.packages("remotes", repos = cran_repos, quiet = TRUE)
    }
    remotes::install_github(github_fallbacks[[pkg]], quiet = TRUE, upgrade = "never")
    return(invisible(TRUE))
  }
  invisible(TRUE)
}

install_missing <- function(pkgs) {
  missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) == 0) {
    message("All requested packages are already installed.")
    return(invisible(character()))
  }
  message("Installing missing packages: ", paste(missing, collapse = ", "))
  for (pkg in missing) {
    tryCatch(
      install_one(pkg),
      error = function(e) {
        message("  - failed to install ", pkg, ": ", conditionMessage(e))
      }
    )
  }
  invisible(missing)
}

load_packages <- function(pkgs) {
  for (pkg in pkgs) {
    suppressPackageStartupMessages(library(pkg, character.only = TRUE))
  }
}

root <- normalizePath(getwd(), winslash = "/", mustWork = FALSE)

if (install_pkgs) {
  install_missing(required)
}

loaded <- character()
for (pkg in required) {
  if (requireNamespace(pkg, quietly = TRUE)) {
    suppressPackageStartupMessages(library(pkg, character.only = TRUE))
    loaded <- c(loaded, pkg)
  }
}

out_dir <- file.path(root, "Output", "audits")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

manifest <- data.frame(
  package = loaded,
  version = vapply(loaded, function(p) as.character(utils::packageVersion(p)), character(1)),
  stringsAsFactors = FALSE
)

manifest_path <- file.path(out_dir, "plant_r_setup_packages.csv")
utils::write.csv(manifest, manifest_path, row.names = FALSE)

session_path <- file.path(out_dir, "plant_r_setup_sessionInfo.txt")
sink(session_path)
cat("Plant R setup\n\n")
cat("Root: ", root, "\n\n", sep = "")
print(sessionInfo())
sink()

cat("Loaded packages: ", paste(loaded, collapse = ", "), "\n", sep = "")
cat("Wrote: ", manifest_path, "\n", sep = "")
cat("Wrote: ", session_path, "\n", sep = "")
cat("\nSuggested sources:\n")
cat("- BIEN: Botanical Information and Ecology Network\n")
cat("- rWCVP / rWCVPdata: World Checklist of Vascular Plants\n")
cat("- expowo: POWO/WCVP mining helper for species lists and country distributions\n")
