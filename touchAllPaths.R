#!/usr/bin/env Rscript
#
# touchAllPaths.R
#
# Given a text file containing one file path per line, create the directory
# hierarchy for each path (relative to the current working directory) and
# touch the file. Useful for pre-creating the output tree expected by a
# pipeline before any jobs have run.
#
# Leading slashes are stripped from each path so that absolute paths in the
# input file are resolved relative to CWD rather than the filesystem root.
#
# Usage:
#   Rscript touchAllPaths.R <paths_file>
#
# Arguments:
#   paths_file  Plain text file with one path per line.
#               Lines are treated as absolute paths; the leading '/' is
#               stripped before creating directories and touching files.
#
# Example:
#   echo -e "/results/sample1/out.txt\n/results/sample2/out.txt" > paths.txt
#   Rscript touchAllPaths.R paths.txt
#   # Creates ./results/sample1/out.txt and ./results/sample2/out.txt
#

require(tidyverse)

usage <- "
Usage: Rscript touchAllPaths.R <paths_file>

  paths_file  Text file with one absolute path per line.
              Directories are created and files are touched
              relative to the current working directory
              (leading slash is stripped from each path).
"

argv <- commandArgs(trailingOnly = TRUE)

if (length(argv) < 1) {
  cat(usage)
  quit(status = 1)
}

paths <- scan(argv[1], "", sep = "\n")

for (path in paths) {
  cat("creating", path, "...")
  # Strip leading slash so paths resolve relative to CWD, not filesystem root
  dir <- gsub("^/", "", dirname(path))
  fs::dir_create(dir)
  fs::file_touch(file.path(dir, basename(path)))
  cat("\n")
}
