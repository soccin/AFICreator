# AFICreator v5.2.0

Generates HALO stitching manifest files (`.afi`) from directories of TIFF
images. Automates the tedious process of importing TIFF stacks and naming
imaging channels for the HALO image analysis platform used in multiplexed
immunofluorescence microscopy.

## Usage

```bash
python3 afi_v5.py <input_dir> [options]
```

### Options

| Flag | Description |
|---|---|
| `--mode` | Filename convention: `halov5` (default), `legacy`, or `hodgkin` |
| `--output-dir DIR` | Write all `.afi` files here (default: alongside the TIFFs) |
| `--num-stains N` | Warn and skip spots that don't have exactly N files |
| `--dry-run` | Print what would be written without creating any files |
| `--verbose` | Print one line per spot processed |
| `--pattern REGEX` | Override the mode's default filename regex |

### Examples

```bash
# ABTC cohort data (default mode)
python3 afi_v5.py /data/ABTC_001 --mode halov5

# Preview what would be generated, then write
python3 afi_v5.py /data/slides --mode halov5 --dry-run --verbose
python3 afi_v5.py /data/slides --mode halov5 --output-dir /results/afi

# Multiple input directories (comma-separated also works)
python3 afi_v5.py /data/batch1 /data/batch2 --mode legacy

# Validate stain count before writing
python3 afi_v5.py /data/slides --mode halov5 --num-stains 38
```

## Filename Conventions

### `--mode halov5`
```
SAMPLE_CYCLE.minor.patch_RSPOT_DYE_MARKER_FINAL_*.tif
Example: ABTC_001_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.tif → channel "ERG"
```
The dye prefix (e.g. `Cy3_`) is stripped from the channel name. Only files
containing `_FINAL_` are processed; earlier intermediates are skipped.

### `--mode legacy`
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

## Testing

```bash
python3 -m pytest tests/ -v
```

The test suite lives in `tests/` and requires `pytest` (`pip install pytest`).
It runs automatically without touching any production data directories.

```
tests/
    conftest.py            # shared fixtures (input/golden paths)
    test_unit.py           # pure-function tests (no I/O)
    test_integration.py    # end-to-end golden-file test
    data/
        CD_PDX_010/
            CD_PDX_010_Final/   # 488 input .ome.tif files
        CD_PDX_010_expected/    # 8 reference .afi files (Spot0-Spot7)
```

The integration test runs `afi_v5.py` against the `CD_PDX_010` dataset,
writes output to a temporary directory, and compares every generated `.afi`
against the reference files in `tests/data/CD_PDX_010_expected/`.

## Requirements

Python 3.9+, standard library only (`os`, `re`, `argparse`,
`xml.etree.ElementTree`).

