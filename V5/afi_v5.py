"""afi_v5.py — Generate HALO stitching manifest (.afi) files from TIFF directories.

This script traverses one or more directories of TIFF images, groups them by
spot/ROI number, and writes XML .afi manifest files that HALO uses to import
multiplexed immunofluorescence image stacks.

Three filename conventions are supported via --mode:

  generic   L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif
  abtc      ABTC_001_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.tif
  hodgkin   B2M_AFRemoved_pyr16_spot_001.tif  (+ DAPI variant)

Usage examples:
  python3 afi_v5.py /data/slides --mode abtc
  python3 afi_v5.py /data/slides --mode generic --num-stains 38 --output-dir /tmp/out
  python3 afi_v5.py /data/slides --mode hodgkin --dry-run --verbose
  python3 afi_v5.py dir1,dir2,dir3 --mode abtc           # comma-separated dirs
"""

import argparse
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Optional

if sys.version_info < (3, 9):
    sys.exit("afi_v5.py requires Python 3.9 or later (for ET.indent support)")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BIT_DEPTH = "16"  # hardcoded; all HALO-compatible TIFFs in this workflow are 16-bit

# ---------------------------------------------------------------------------
# Regex patterns
#
# All patterns use named groups (?P<name>...) so each captured field is
# self-documenting and accessible by name rather than by positional index.
# ---------------------------------------------------------------------------

# -- Generic pattern --------------------------------------------------------
# Matches the general-purpose filename convention from afi_v2.py.
#
# Example: L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif
#
# Named groups:
#   sample  — slide/sample identifier; must start with a letter and must not
#             end with an underscore (e.g. "L_001", "GBM_042")
#   cycle   — imaging cycle integer (the major number in the version triple);
#             only the first digit sequence is captured, minor/patch are ignored
#             (e.g. "3" from "3.0.4")
#   spot    — ROI/spot number following the literal character 'R'
#             (e.g. "000" from "R000")
#   marker  — channel name token; any non-whitespace run of characters ending
#             before the bit-depth field (e.g. "CD3", "DAPI")
#
# The version triple dots are now fully escaped (\.\d+\.\d+) — the original
# afi_v2.py had an unescaped dot in the middle position which was a latent bug.
# The bit-depth field (\d+bit) is consumed but not captured; it is always 16.
GENERIC_PATTERN = re.compile(
    r'^(?P<sample>[A-Za-z].+[^_])'  # sample: alpha start, no trailing underscore
    r'_(?P<cycle>\d+)\.\d+\.\d+'    # cycle + ignored version minor.patch
    r'_R(?P<spot>\d+)'              # spot: literal 'R' then integer
    r'_(?P<marker>\S+)'             # marker: non-whitespace channel token
    r'_\d+bit_'                     # bit-depth field — matched but not captured
    r'.*\.tif$',                    # arbitrary suffix then .tif extension
    re.IGNORECASE,
)

# -- ABTC pattern -----------------------------------------------------------
# Matches the ABTC brain-tumor-cohort filename convention from afi_v2_ABTC_Version.py.
# The key structural difference from generic is:
#   (a) a combined dye+marker field instead of a plain marker field
#   (b) a required "_FINAL_" token — files without it are non-processed
#       intermediates and must be silently skipped
#
# Examples:
#   ABTC_001_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.tif    → channel "ERG"
#   ABTC_001_1.0.4_R000_FITC_CD68_FINAL_AFR_F.tif  → channel "CD68"
#   ABTC_001_18.0.4_R000_DAPI__FINAL_F.tif          → channel "DAPI18"
#
# Named groups:
#   sample      — slide identifier (same rule as generic)
#   cycle       — imaging cycle number (e.g. "18" from "18.0.4")
#   spot        — ROI number after literal 'R'
#   dye_marker  — combined dye+marker field.  Examples:
#                   "Cy3_ERG"   → dye=Cy3,  marker=ERG
#                   "FITC_CD68" → dye=FITC, marker=CD68
#                   "DAPI_"     → DAPI file; the trailing underscore before
#                                 _FINAL_ is absorbed into this group,
#                                 yielding "DAPI_" not "DAPI"
#   final_flag  — the literal "FINAL" token; its presence confirms the file
#                 is a processed image ready for HALO import
#
# IMPORTANT — DAPI double-underscore edge case:
#   DAPI files have the pattern DAPI__FINAL_ (two underscores).
#   The regex sees "_DAPI__FINAL_" and captures dye_marker="DAPI_".
#   The channel extractor checks for "dapi" BEFORE attempting dye-stripping;
#   if that guard were absent, split("_") on "DAPI_" would yield ["DAPI", ""]
#   and rejoin of [1:] would produce an empty string.
ABTC_PATTERN = re.compile(
    r'^(?P<sample>[A-Za-z].+[^_])'       # sample
    r'_(?P<cycle>\d+)\.\d+\.\d+'         # cycle + ignored version minor.patch
    r'_R(?P<spot>\d+)'                   # spot
    r'_(?P<dye_marker>\S+)'              # dye+marker combined field
    r'_(?P<final_flag>FINAL|_FINAL)_'    # required FINAL sentinel; skips non-final files
    r'.*\.tif$',                          # arbitrary suffix then .tif
    re.IGNORECASE,
)

# -- Hodgkin patterns (two separate patterns) --------------------------------
# The Hodgkin convention (from V4/afi_hodgkin___v4.py) uses structurally
# different filenames for DAPI vs non-DAPI channels, requiring two regexes.
# DAPI detection is done first by substring search ("dapi" in filename)
# before either regex is attempted.
#
# Additionally, the sample name is NOT present in hodgkin filenames.
# It is derived from the last path component of the containing directory
# (e.g. /slides/GBM_Cohort1 → sample="GBM_Cohort1").

# Hodgkin non-DAPI marker files.
#
# Example: B2M_AFRemoved_pyr16_spot_001.tif
#
# Named groups:
#   marker  — full marker name; greedy, captures everything before _AFRemoved_
#             (e.g. "B2M", "CD45", "PD-L1")
#   spot    — zero-padded spot number immediately before .tif
#             (e.g. "001" from "spot_001.tif")
HODGKIN_MARKER_PATTERN = re.compile(
    r'^(?P<marker>.+)'       # marker: greedy up to _AFRemoved_
    r'_AFRemoved_'           # literal separator; "AF" = autofluorescence removed
    r'.*_spot_'              # ignored processing tokens (e.g. "pyr16")
    r'(?P<spot>\d+)\.tif$',  # spot number
)

# Hodgkin DAPI files.
# Detected by "dapi" substring check BEFORE this regex is applied.
#
# Example: S037_mono_dapi_reg_pyr16_spot_001.tif
#
# Named groups:
#   cycle  — cycle number embedded after the literal 'S' prefix, up to the
#             first underscore (e.g. "037" from "S037_..." → channel "DAPI37")
#   spot   — spot number immediately before .tif
HODGKIN_DAPI_PATTERN = re.compile(
    r'^S(?P<cycle>[^_]+)'   # cycle: after literal 'S', up to first underscore
    r'_.*_spot_'            # ignored tokens
    r'(?P<spot>\d+)\.tif$',
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TiffRecord:
    """All information needed to write one <Image> element in an .afi file.

    Attributes:
        sample:   Slide/sample identifier, used in the output .afi filename.
        spot:     Spot/ROI number as an integer (e.g. 0, 1, 37).
        channel:  Fully resolved channel name for <ChannelName>
                  (e.g. "CD3", "DAPI18", "B2M").
        filename: Bare filename (no directory path) for the <Path> element.
        dirpath:  Absolute path to the directory containing this file.
                  Used as write location when --output-dir is not specified.
    """

    sample: str
    spot: int
    channel: str
    filename: str
    dirpath: str


# SpotLedger maps spot integer → list of TiffRecords for that spot.
# All records in one list share the same sample name and dirpath.
SpotLedger = dict[int, list[TiffRecord]]


@dataclass
class ModeConfig:
    """Bundles the compiled regex(es) and channel extractor for one naming mode.

    Attributes:
        pattern:              Primary compiled regex for non-DAPI files (all modes)
                              and for all files in generic/abtc modes.
        pattern_dapi:         Secondary compiled regex for DAPI files.
                              Only used in hodgkin mode; None in generic/abtc.
        extract_channel:      Callable that receives a successful re.Match against
                              `pattern` and returns the resolved channel name string.
        extract_channel_dapi: Callable for DAPI matches (hodgkin only). None otherwise.
        sample_from_dir:      When True, the sample name is taken from the last
                              component of the directory path instead of from the
                              regex match. True only in hodgkin mode.
    """

    pattern: re.Pattern
    pattern_dapi: Optional[re.Pattern]
    extract_channel: Callable[[re.Match], str]
    extract_channel_dapi: Optional[Callable[[re.Match], str]]
    sample_from_dir: bool = False


# ---------------------------------------------------------------------------
# Channel extractor functions
# ---------------------------------------------------------------------------


def extract_channel_generic(match: re.Match) -> str:
    """Resolve channel name for a generic-mode filename match.

    DAPI files are detected by the marker field containing "dapi" (case-insensitive).
    Their channel is named "DAPI" followed by the integer cycle number, e.g. "DAPI3".
    All other markers are returned verbatim from the match.

    Args:
        match: Successful match against GENERIC_PATTERN.

    Returns:
        Resolved channel name string.
    """
    marker = match.group("marker")
    if "dapi" in marker.lower():
        return f"DAPI{int(match.group('cycle'))}"
    return marker


def extract_channel_abtc(match: re.Match) -> str:
    """Resolve channel name for an ABTC-mode filename match.

    The dye_marker group contains the combined dye+marker token, e.g.:
      "Cy3_ERG"   → strip "Cy3"  → "ERG"
      "FITC_CD68" → strip "FITC" → "CD68"
      "DAPI_"     → DAPI guard fires → "DAPI18"  (cycle from match)

    The DAPI guard (substring check) MUST run before dye-stripping because
    DAPI filenames yield dye_marker="DAPI_" (trailing underscore from the
    double-underscore in the filename). Stripping the first token of "DAPI_"
    on "_" gives ["DAPI", ""] and rejoining [1:] produces an empty string.

    For non-DAPI markers with no underscore in the dye_marker field, the full
    token is returned unchanged (defensive fallback; not seen in practice).

    Args:
        match: Successful match against ABTC_PATTERN.

    Returns:
        Resolved channel name string.
    """
    dye_marker = match.group("dye_marker")
    # DAPI guard must come first — see docstring for why ordering is load-bearing.
    if "dapi" in dye_marker.lower():
        return f"DAPI{int(match.group('cycle'))}"
    parts = dye_marker.split("_")
    # Drop the leading dye token (e.g. "Cy3") and rejoin the rest.
    return "_".join(parts[1:]) if len(parts) > 1 else dye_marker


def extract_channel_hodgkin_marker(match: re.Match) -> str:
    """Return the marker name for a non-DAPI hodgkin file match.

    Args:
        match: Successful match against HODGKIN_MARKER_PATTERN.

    Returns:
        Marker group verbatim (e.g. "B2M", "CD45").
    """
    return match.group("marker")


def extract_channel_hodgkin_dapi(match: re.Match) -> str:
    """Return the DAPI channel name for a hodgkin DAPI file match.

    Args:
        match: Successful match against HODGKIN_DAPI_PATTERN.

    Returns:
        "DAPI" followed by the integer cycle number (e.g. "DAPI37").
    """
    return f"DAPI{int(match.group('cycle'))}"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _compile_pattern(value: str) -> re.Pattern:
    """Compile a user-supplied regex string, used as argparse type= function.

    Args:
        value: Regular expression string from the command line.

    Returns:
        Compiled re.Pattern.

    Raises:
        argparse.ArgumentTypeError: If the pattern fails to compile.
    """
    try:
        return re.compile(value, re.IGNORECASE)
    except re.error as exc:
        raise argparse.ArgumentTypeError(f"Invalid regex pattern: {exc}") from exc


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed namespace with all arguments as attributes.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Generate HALO .afi manifest files from directories of TIFF images. "
            "Traverses input directories recursively, groups TIFFs by spot/ROI "
            "number, and writes one XML .afi file per spot."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Filename convention examples:\n"
            "  generic:  L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif\n"
            "  abtc:     ABTC_001_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.tif\n"
            "  hodgkin:  B2M_AFRemoved_pyr16_spot_001.tif\n"
            "            S037_mono_dapi_reg_pyr16_spot_001.tif\n"
        ),
    )

    parser.add_argument(
        "input_dirs",
        nargs="+",
        metavar="DIR",
        help=(
            "One or more directories to scan recursively for TIFF files. "
            "Comma-separated paths within a single argument are also accepted "
            "(e.g. 'dir1,dir2,dir3') for shell compatibility."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["generic", "abtc", "hodgkin"],
        default="abtc",
        help=(
            "Filename convention to use when parsing TIFF filenames. "
            "Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=None,
        help=(
            "Directory where all .afi files are written. "
            "If omitted, each .afi is written into the same directory as "
            "the TIFF files it references."
        ),
    )
    parser.add_argument(
        "--num-stains",
        type=int,
        metavar="N",
        default=None,
        help=(
            "Expected number of TIFF files per spot. Spots with a different "
            "count emit a warning and are skipped. Omit to process all spots "
            "regardless of file count."
        ),
    )
    parser.add_argument(
        "--pattern",
        type=_compile_pattern,
        metavar="REGEX",
        default=None,
        help=(
            "Override the mode's default primary regex with a custom pattern. "
            "Must use the same named groups as the chosen --mode: "
            "generic/abtc require at minimum sample, cycle, spot, and either "
            "marker (generic) or dye_marker (abtc). "
            "hodgkin mode requires marker and spot; use --pattern-dapi for "
            "the DAPI override."
        ),
    )
    parser.add_argument(
        "--pattern-dapi",
        type=_compile_pattern,
        metavar="REGEX",
        default=None,
        help=(
            "Override the hodgkin DAPI pattern. Only valid with "
            "--mode hodgkin and --pattern. "
            "Must provide named groups: cycle, spot."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what .afi files would be written without creating any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print one line per spot processed.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Mode configuration
# ---------------------------------------------------------------------------


def build_mode_config(args: argparse.Namespace) -> ModeConfig:
    """Construct a ModeConfig from parsed arguments.

    Applies --pattern and --pattern-dapi overrides if provided.

    Args:
        args: Parsed argument namespace from parse_args().

    Returns:
        Fully populated ModeConfig for the selected mode.

    Raises:
        SystemExit: For invalid flag combinations (e.g. --pattern-dapi without hodgkin).
    """
    if args.pattern_dapi is not None and args.mode != "hodgkin":
        sys.exit("ERROR: --pattern-dapi is only valid with --mode hodgkin")

    if args.mode == "generic":
        config = ModeConfig(
            pattern=GENERIC_PATTERN,
            pattern_dapi=None,
            extract_channel=extract_channel_generic,
            extract_channel_dapi=None,
            sample_from_dir=False,
        )
    elif args.mode == "abtc":
        config = ModeConfig(
            pattern=ABTC_PATTERN,
            pattern_dapi=None,
            extract_channel=extract_channel_abtc,
            extract_channel_dapi=None,
            sample_from_dir=False,
        )
    else:  # hodgkin
        config = ModeConfig(
            pattern=HODGKIN_MARKER_PATTERN,
            pattern_dapi=HODGKIN_DAPI_PATTERN,
            extract_channel=extract_channel_hodgkin_marker,
            extract_channel_dapi=extract_channel_hodgkin_dapi,
            sample_from_dir=True,
        )

    # Apply user-supplied pattern overrides.
    if args.pattern is not None:
        config.pattern = args.pattern
    if args.pattern_dapi is not None:
        config.pattern_dapi = args.pattern_dapi

    return config


# ---------------------------------------------------------------------------
# TIFF matching
# ---------------------------------------------------------------------------


def match_tiff(
    filename: str,
    dirpath: str,
    config: ModeConfig,
) -> Optional[TiffRecord]:
    """Attempt to parse a TIFF filename into a TiffRecord.

    For hodgkin mode, checks for "dapi" in the filename first and routes to
    the DAPI pattern; non-DAPI files use the primary marker pattern.
    For generic and abtc modes, only the primary pattern is tried.

    Files that do not match are silently returned as None (skipped).

    Args:
        filename: Bare filename without directory component.
        dirpath:  Absolute path to the directory containing the file.
        config:   ModeConfig with compiled patterns and extractors.

    Returns:
        A TiffRecord if the filename matches, otherwise None.
    """
    if not filename.lower().endswith(".tif"):
        return None

    if config.sample_from_dir:
        # Hodgkin mode: sample name comes from the directory, not the filename.
        sample = os.path.basename(os.path.abspath(dirpath))
        is_dapi = "dapi" in filename.lower()

        if is_dapi:
            if config.pattern_dapi is None:
                return None
            m = config.pattern_dapi.search(filename)
            if m is None:
                return None
            try:
                channel = config.extract_channel_dapi(m)
            except (ValueError, IndexError) as exc:
                print(
                    f"WARNING: Could not extract DAPI channel from '{filename}': {exc}",
                    file=sys.stderr,
                )
                return None
        else:
            m = config.pattern.search(filename)
            if m is None:
                return None
            try:
                channel = config.extract_channel(m)
            except (ValueError, IndexError) as exc:
                print(
                    f"WARNING: Could not extract channel from '{filename}': {exc}",
                    file=sys.stderr,
                )
                return None

        try:
            spot = int(m.group("spot"))
        except (ValueError, IndexError) as exc:
            print(
                f"WARNING: Could not parse spot number from '{filename}': {exc}",
                file=sys.stderr,
            )
            return None

    else:
        # Generic / ABTC mode: sample name is captured from the filename itself.
        m = config.pattern.match(filename)
        if m is None:
            return None

        try:
            sample = m.group("sample")
            spot = int(m.group("spot"))
            channel = config.extract_channel(m)
        except (ValueError, IndexError) as exc:
            print(
                f"WARNING: Could not parse fields from '{filename}': {exc}",
                file=sys.stderr,
            )
            return None

    return TiffRecord(
        sample=sample,
        spot=spot,
        channel=channel,
        filename=filename,
        dirpath=dirpath,
    )


# ---------------------------------------------------------------------------
# Spot ledger collection
# ---------------------------------------------------------------------------


def collect_spot_ledger(dirpath: str, config: ModeConfig) -> SpotLedger:
    """Scan one directory for matching TIFFs and group them by spot number.

    Only the immediate files in dirpath are examined; directory recursion is
    handled by the caller via os.walk.

    Args:
        dirpath: Directory path to scan.
        config:  ModeConfig with patterns and extractors.

    Returns:
        Dict mapping spot integer → list of TiffRecord.
        Empty dict if no files match.
    """
    ledger: SpotLedger = {}
    try:
        entries = os.listdir(dirpath)
    except PermissionError as exc:
        print(f"WARNING: Cannot read directory '{dirpath}': {exc}", file=sys.stderr)
        return ledger

    for filename in sorted(entries):
        filepath = os.path.join(dirpath, filename)
        if not os.path.isfile(filepath):
            continue
        record = match_tiff(filename, dirpath, config)
        if record is None:
            continue
        ledger.setdefault(record.spot, []).append(record)

    return ledger


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------


def build_xml(sample: str, spot: int, records: list[TiffRecord]) -> ET.Element:
    """Build an <ImageList> ElementTree element for one spot's channel set.

    Channels are sorted alphabetically by channel name before insertion,
    matching the sort order used by afi_v2.py and afi_v2_ABTC_Version.py.
    ET.indent produces tab-indented output matching the reference test.afi format.

    Args:
        sample:  Sample name (used in error messages only).
        spot:    Spot number (used in error messages only).
        records: Non-empty list of TiffRecord for this spot.

    Returns:
        Root <ImageList> ET.Element, indented with tabs.
    """
    root = ET.Element("ImageList")

    for record in sorted(records, key=lambda r: r.channel):
        img = ET.SubElement(root, "Image")
        ET.SubElement(img, "Path").text = record.filename
        ET.SubElement(img, "BitDepth").text = BIT_DEPTH
        ET.SubElement(img, "ChannelName").text = record.channel

    ET.indent(root, space="\t")
    return root


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------


def write_afi(
    output_dir: Optional[str],
    sample: str,
    spot: int,
    records: list[TiffRecord],
    dry_run: bool = False,
) -> pathlib.Path:
    """Write one .afi XML file for a single spot.

    The output filename is "{sample}_Spot{spot}.afi" where spot is an integer
    with no zero-padding (e.g. "ABTC_001_Spot0.afi", not "ABTC_001_Spot000.afi").

    Args:
        output_dir: Directory to write the .afi file; if None, the .afi is
                    written into the same directory as the TIFF files.
        sample:     Sample name embedded in the output filename.
        spot:       Spot number embedded in the output filename.
        records:    Non-empty list of TiffRecord for this spot.
        dry_run:    If True, prints the target path but does not write.

    Returns:
        Path to the .afi file (written or would-be written in dry-run mode).

    Raises:
        ValueError: If records is empty.
    """
    if not records:
        raise ValueError(f"No records provided for {sample} spot {spot}")

    write_dir = output_dir if output_dir is not None else records[0].dirpath
    afi_filename = f"{sample}_Spot{spot}.afi"
    afi_path = pathlib.Path(write_dir) / afi_filename

    if dry_run:
        print(f"[dry-run] Would write: {afi_path}  ({len(records)} channels)")
        return afi_path

    root = build_xml(sample, spot, records)
    tree = ET.ElementTree(root)
    # xml_declaration=False: the reference test.afi has no <?xml ...?> header.
    tree.write(str(afi_path), encoding="unicode", xml_declaration=False)
    # ET.ElementTree.write does not append a trailing newline; add two to match
    # the reference file format (one after </ImageList>, one blank line).
    with open(afi_path, "a") as fh:
        fh.write("\n\n")

    return afi_path


# ---------------------------------------------------------------------------
# Directory processing
# ---------------------------------------------------------------------------


def process_directory(
    dirpath: str,
    output_dir: Optional[str],
    config: ModeConfig,
    num_stains: Optional[int],
    dry_run: bool,
    verbose: bool,
) -> int:
    """Collect TIFFs in one directory, validate per-spot counts, write .afi files.

    Args:
        dirpath:    Absolute path to one directory from the os.walk traversal.
        output_dir: Global output directory override; None means write alongside TIFFs.
        config:     ModeConfig with patterns and extractors.
        num_stains: If set, skip spots whose TIFF count differs from this value.
        dry_run:    If True, do not write any files.
        verbose:    If True, print one line per spot.

    Returns:
        Number of .afi files written (or that would be written in dry-run mode).
    """
    ledger = collect_spot_ledger(dirpath, config)
    if not ledger:
        return 0

    written = 0

    for spot in sorted(ledger):
        records = ledger[spot]
        # All records in one spot share the same sample name (guaranteed by
        # how the ledger is built from a single directory scan).
        sample = records[0].sample

        # Stain-count validation: skip this spot if the file count doesn't
        # match the expected number of stains, and warn the user.
        if num_stains is not None and len(records) != num_stains:
            print(
                f"WARNING: Spot {spot} ({sample}) has {len(records)} files, "
                f"expected {num_stains}; skipping.",
                file=sys.stderr,
            )
            continue

        # Duplicate channel detection: two files with the same channel name in
        # one spot would produce an ambiguous .afi entry.  Skip the spot and warn.
        channel_names = [r.channel for r in records]
        seen: set[str] = set()
        duplicates = [c for c in channel_names if c in seen or seen.add(c)]
        if duplicates:
            print(
                f"WARNING: Duplicate channel(s) {sorted(set(duplicates))} in "
                f"spot {spot} ({sample}) at '{dirpath}'; skipping.",
                file=sys.stderr,
            )
            continue

        afi_path = write_afi(output_dir, sample, spot, records, dry_run)
        written += 1

        if verbose and not dry_run:
            print(f"  Wrote: {afi_path}  ({len(records)} channels)")

    return written


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments, validate inputs, walk directories, write AFI files."""
    args = parse_args()

    # Validate the output directory early so we fail fast before any scanning.
    if args.output_dir is not None:
        if not os.path.isdir(args.output_dir):
            sys.exit(f"ERROR: Output directory does not exist: '{args.output_dir}'")

    # Flatten input_dirs: each positional arg may itself be comma-separated
    # (e.g. "dir1,dir2") to support shell quoting styles from the old GUI.
    input_dirs: list[str] = [
        p.strip()
        for entry in args.input_dirs
        for p in entry.split(",")
        if p.strip()
    ]

    # Validate all input directories before starting any work.
    bad_dirs = [d for d in input_dirs if not os.path.isdir(d)]
    if bad_dirs:
        for d in bad_dirs:
            print(f"ERROR: Input directory does not exist: '{d}'", file=sys.stderr)
        sys.exit(1)

    config = build_mode_config(args)

    total_written = 0
    total_dirs_scanned = 0

    for input_dir in input_dirs:
        for dirpath, _subdirs, _files in os.walk(input_dir):
            total_dirs_scanned += 1
            if args.verbose:
                print(f"Scanning: {dirpath}")
            total_written += process_directory(
                dirpath=dirpath,
                output_dir=args.output_dir,
                config=config,
                num_stains=args.num_stains,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

    action = "would be written" if args.dry_run else "written"
    print(f"Done. {total_written} .afi file(s) {action} "
          f"({total_dirs_scanned} director{'y' if total_dirs_scanned == 1 else 'ies'} scanned).")


if __name__ == "__main__":
    main()
