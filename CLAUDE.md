# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AFICreator generates HALO stitching manifest files (`.afi` files) from directories of TIFF images. It automates the tedious process of importing TIFF stacks and naming imaging channels for the HALO image analysis platform used in multiplexed immunofluorescence microscopy.

## Running

**GUI version (primary):**
```bash
python3 afi_v2.py
```
Opens a Tkinter window with fields for input directory, output directory, and number of stains.

**ABTC-specific variant:**
```bash
python3 afi_v2_ABTC_Version.py
```

**CLI version (no GUI):**
```bash
cd /path/where/afi/files/should/be/written
python3 V4/afi_hodgkin___v4.py /path/to/images
```

**Tkinter missing:** Install via `brew install python-tk`, not pip.

## Architecture

Three active implementations with no shared library — each is a self-contained script:

- **`afi_v2.py`** — general-purpose GUI; the canonical version
- **`afi_v2_ABTC_Version.py`** — GUI variant for ABTC filename conventions
- **`V4/afi_hodgkin___v4.py`** — CLI version for automated pipelines
- **`attic/afi.py`** — legacy, Python 2-era, do not modify

All versions follow the same logic: traverse directories → group TIFFs by spot → emit XML `.afi` files named `{SAMPLE}_Spot{N}.afi`.

## Filename Patterns

**Generic (`afi_v2.py`):**
```
SAMPLE_CYCLE.decimal_decimal_RSPOT_MARKER_BITDEPTH.tif
Example: L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif
```

**ABTC variant (`afi_v2_ABTC_Version.py`):**
```
SAMPLE_CYCLE.decimal_decimal_RSPOT_DYE_MARKER_FINAL_*.tif
Example: ABTC_014_1.0.1_R001_Cy3_CD3_FINAL_....tif
```
The DYE prefix (e.g., `Cy3_`) is stripped from the channel name.

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

Channels are sorted alphabetically within each spot. Bit depth is hardcoded to 16.

## Test Data

Example TIFFs are in `test/ABTC_001/` (282 files). Reference output is `test.afi`.

## Dependencies

Python 3 stdlib only: `os`, `re`, `xml.etree.ElementTree`, `tkinter`.
