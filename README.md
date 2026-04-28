# AFICreator

Generates HALO stitching manifest files (`.afi`) from directories of TIFF
images. Automates the tedious process of importing TIFF stacks and naming
imaging channels for the HALO image analysis platform used in multiplexed
immunofluorescence microscopy.

## Usage

```bash
python3 V5/afi_v5.py <input_dir> [options]
```

### Options

| Flag | Description |
|---|---|
| `--mode` | Filename convention: `abtc` (default), `generic`, or `hodgkin` |
| `--output-dir DIR` | Write all `.afi` files here (default: alongside the TIFFs) |
| `--num-stains N` | Warn and skip spots that don't have exactly N files |
| `--dry-run` | Print what would be written without creating any files |
| `--verbose` | Print one line per spot processed |
| `--pattern REGEX` | Override the mode's default filename regex |

### Examples

```bash
# ABTC cohort data (default mode)
python3 V5/afi_v5.py /data/ABTC_001 --mode abtc

# Preview what would be generated, then write
python3 V5/afi_v5.py /data/slides --mode abtc --dry-run --verbose
python3 V5/afi_v5.py /data/slides --mode abtc --output-dir /results/afi

# Multiple input directories (comma-separated also works)
python3 V5/afi_v5.py /data/batch1 /data/batch2 --mode generic

# Validate stain count before writing
python3 V5/afi_v5.py /data/slides --mode abtc --num-stains 38
```

## Filename Conventions

### `--mode abtc`
```
SAMPLE_CYCLE.minor.patch_RSPOT_DYE_MARKER_FINAL_*.tif
Example: ABTC_001_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.tif → channel "ERG"
```
The dye prefix (e.g. `Cy3_`) is stripped from the channel name. Only files
containing `_FINAL_` are processed; earlier intermediates are skipped.

### `--mode generic`
```
SAMPLE_CYCLE.minor.patch_RSPOT_MARKER_16bit_*.tif
Example: L_001_3.0.4_R000_CD3_16bit_AFRemoved.tif → channel "CD3"
```

### `--mode hodgkin`
```
MARKER_AFRemoved_*_spot_N.tif          (non-DAPI)
SCYCLE_*_dapi_*_spot_N.tif            (DAPI)
```
Sample name is taken from the containing directory name.

## Output

One `.afi` file per spot, named `{SAMPLE}_Spot{N}.afi`:

```xml
<ImageList>
    <Image>
        <Path>filename.tif</Path>
        <BitDepth>16</BitDepth>
        <ChannelName>MARKER</ChannelName>
    </Image>
</ImageList>
```

Channels are sorted alphabetically within each spot.

## Requirements

Python 3.9+, standard library only (`os`, `re`, `argparse`,
`xml.etree.ElementTree`).

## Older Versions

Earlier GUI-based scripts (`afi_v2.py`, `afi_v2_ABTC_Version.py`) and the
previous CLI version (`V4/afi_hodgkin___v4.py`) have been moved to `attic/`
for reference. Use V5 for all new work.
