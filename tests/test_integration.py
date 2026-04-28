"""Integration test: run afi_v5.py against CD_PDX_010 and compare to golden output."""

import subprocess
import sys
import xml.etree.ElementTree as ET


def _parse_images(afi_path):
    """Return list of (Path, BitDepth, ChannelName) tuples from an .afi file."""
    root = ET.parse(str(afi_path)).getroot()
    return [
        (
            img.findtext("Path"),
            img.findtext("BitDepth"),
            img.findtext("ChannelName"),
        )
        for img in root.findall("Image")
    ]


def assert_afi_equal(produced, golden):
    produced_images = _parse_images(produced)
    golden_images = _parse_images(golden)

    assert len(produced_images) == len(golden_images), (
        f"{produced.name}: got {len(produced_images)} channels, "
        f"expected {len(golden_images)}"
    )

    for i, (p, g) in enumerate(zip(produced_images, golden_images)):
        assert p == g, (
            f"{produced.name} Image[{i}] mismatch:\n"
            f"  produced: Path={p[0]!r}  BitDepth={p[1]!r}  Channel={p[2]!r}\n"
            f"  golden:   Path={g[0]!r}  BitDepth={g[1]!r}  Channel={g[2]!r}"
        )


def test_cd_pdx_010_halov5(tmp_path, input_dir, golden_dir):
    result = subprocess.run(
        [
            sys.executable,
            "afi_v5.py",
            str(input_dir),
            "--mode", "halov5",
            "--output-dir", str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"afi_v5.py failed:\n{result.stderr}"

    for spot in range(8):
        name = f"CD_PDX_010_Spot{spot}.afi"
        produced = tmp_path / name
        golden = golden_dir / name
        assert produced.exists(), f"{name} was not generated"
        assert_afi_equal(produced, golden)
