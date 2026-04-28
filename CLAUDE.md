# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AFICreator generates HALO stitching manifest files (`.afi` files) from directories of TIFF images. It automates the tedious process of importing TIFF stacks and naming imaging channels for the HALO image analysis platform used in multiplexed immunofluorescence microscopy.

## Running

```bash
python3 afi_v5.py <input_dir> [options]
```

### Key options

| Flag | Description |
|---|---|
| `--mode` | Filename convention: `halov5` (default), `legacy`, or `hodgkin` |
| `--output-dir DIR` | Write `.afi` files here (default: alongside the TIFFs) |
| `--num-stains N` | Skip spots that don't have exactly N files |
| `--dry-run` | Print what would be written without creating files |
| `--verbose` | Print one line per spot processed |

## Architecture

Single self-contained CLI script: `afi_v5.py`.

Logic: traverse directories → group TIFFs by spot → filter DAPI to first and last cycle only → emit XML `.afi` files named `{SAMPLE}_Spot{N}.afi`.

## Filename Patterns

**`--mode halov5` (default):**
```
SAMPLE_CYCLE.minor.patch_RSPOT_DYE_MARKER_FINAL_*.tif
Example: ABTC_014_1.0.1_R001_Cy3_CD3_FINAL_....tif
```
The DYE prefix (e.g., `Cy3_`) is stripped from the channel name. Only files containing `_FINAL_` are processed.

**`--mode legacy`:**
```
SAMPLE_CYCLE.minor.patch_RSPOT_MARKER_BITDEPTH.tif
Example: L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif
```

**`--mode hodgkin`:**
```
MARKER_AFRemoved_*_spot_N.tif     (non-DAPI)
SCYCLE_*_dapi_*_spot_N.tif       (DAPI)
```
Sample name is taken from the containing directory name.

## Output Format

```xml
<ImageList>
  <Image>
    <Path>filename.tif</Path>
    <BitDepth>16</BitDepth>
    <ChannelName>MARKER_NAME</ChannelName>
  </Image>
</ImageList>
```

Channels are sorted alphabetically within each spot. Bit depth is hardcoded to 16. DAPI channels are filtered to first and last cycle only (e.g. DAPI1 and DAPI18); intermediates are dropped.

## Test Data

Example TIFFs are in `test/ABTC_001/` (282 files). Reference output is `test.afi`.

## Dependencies

Python 3.9+ stdlib only: `os`, `re`, `argparse`, `xml.etree.ElementTree`.
