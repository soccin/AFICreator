"""Unit tests for pure functions in afi_v5.py."""

import sys
import pathlib
import xml.etree.ElementTree as ET
from typing import Optional

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from afi_v5 import (
    TiffRecord,
    HALOV5_PATTERN,
    build_xml,
    extract_channel_halov5,
    filter_dapi_records,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _r(channel: str, filename: str = "") -> TiffRecord:
    """Minimal TiffRecord for filter tests."""
    return TiffRecord(
        sample="TEST",
        spot=0,
        channel=channel,
        filename=filename or f"{channel}.tif",
        dirpath="/tmp",
    )


def _channel(filename: str) -> Optional[str]:
    """Return resolved channel name for a halov5 filename, or None if no match."""
    m = HALOV5_PATTERN.search(filename)
    if m is None:
        return None
    return extract_channel_halov5(m)


# ---------------------------------------------------------------------------
# filter_dapi_records
# ---------------------------------------------------------------------------


class TestFilterDapiRecords:
    def test_keeps_first_and_last_drops_intermediates(self):
        records = [_r("ERG"), _r("DAPI1"), _r("DAPI5"), _r("DAPI10"), _r("DAPI12")]
        result = filter_dapi_records(records)
        channels = {r.channel for r in result}
        assert "DAPI1" in channels
        assert "DAPI12" in channels
        assert "DAPI5" not in channels
        assert "DAPI10" not in channels
        assert "ERG" in channels

    def test_single_dapi_cycle_kept_once(self):
        records = [_r("ERG"), _r("DAPI12")]
        result = filter_dapi_records(records)
        dapi = [r for r in result if r.channel.startswith("DAPI")]
        assert len(dapi) == 1
        assert dapi[0].channel == "DAPI12"

    def test_no_dapi_passthrough(self):
        records = [_r("ERG"), _r("CD3"), _r("SOX2")]
        result = filter_dapi_records(records)
        assert len(result) == 3
        assert {r.channel for r in result} == {"ERG", "CD3", "SOX2"}

    def test_non_integer_dapi_suffix_passes_through(self):
        records = [_r("DAPIx"), _r("ERG")]
        result = filter_dapi_records(records)
        channels = {r.channel for r in result}
        assert "DAPIx" in channels
        assert "ERG" in channels

    def test_non_dapi_records_appear_before_dapi_in_result(self):
        records = [_r("ERG"), _r("DAPI1"), _r("DAPI12")]
        result = filter_dapi_records(records)
        assert result[0].channel == "ERG"


# ---------------------------------------------------------------------------
# extract_channel_halov5 via HALOV5_PATTERN
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("CD_PDX_010_1.0.4_R000_Cy3_ERG_FINAL_AFR_F.ome.tif", "ERG"),
        ("CD_PDX_010_1.0.4_R000_Cy5_CD40_FINAL_AFR_F.ome.tif", "CD40"),
        ("CD_PDX_010_2.0.4_R000_FITC_CD68_FINAL_AFR_F.ome.tif", "CD68"),
        ("CD_PDX_010_12.0.4_R000_Cy3_CD45-H_FINAL_AFR_F.ome.tif", "CD45-H"),
        ("CD_PDX_010_7.0.4_R000_Cy3_P-RB_FINAL_AFR_F.ome.tif", "P-RB"),
        # DAPI: double underscore variant (cycle 1)
        ("CD_PDX_010_1.0.4_R000_DAPI__FINAL_F.ome.tif", "DAPI1"),
        # DAPI: cycle 12 (max in this dataset)
        ("CD_PDX_010_12.0.4_R000_DAPI__FINAL_F.ome.tif", "DAPI12"),
    ],
)
def test_extract_channel_halov5_matches(filename: str, expected: str):
    assert _channel(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        # No _FINAL_ sentinel — pre-registration file, must be skipped
        "CD_PDX_010_0.0.3_R000_10X_Cy3_F.ome.tif",
        # Non-FINAL DAPI (cycle 1.0.1 variant)
        "CD_PDX_010_1.0.1_R000_DAPI_AF_F.ome.tif",
        # Tiled overview
        "CD_PDX_010_0.0.2_R000_DAPI_F_Tiled.tif",
    ],
)
def test_extract_channel_halov5_no_match(filename: str):
    assert _channel(filename) is None


# ---------------------------------------------------------------------------
# build_xml
# ---------------------------------------------------------------------------


class TestBuildXml:
    def _records(self, channels):
        return [_r(ch, f"{ch}.tif") for ch in channels]

    def test_channels_sorted_alphabetically(self):
        records = self._records(["SOX2", "B7H3", "CD3", "DAPI1"])
        root = build_xml("TEST", 0, records)
        names = [img.findtext("ChannelName") for img in root.findall("Image")]
        assert names == sorted(names)

    def test_all_bit_depths_are_16(self):
        records = self._records(["CD3", "DAPI1", "ERG"])
        root = build_xml("TEST", 0, records)
        depths = {img.findtext("BitDepth") for img in root.findall("Image")}
        assert depths == {"16"}

    def test_path_is_bare_filename(self):
        r = TiffRecord(
            sample="S",
            spot=0,
            channel="CD3",
            filename="CD3.tif",
            dirpath="/some/dir",
        )
        root = build_xml("S", 0, [r])
        path = root.find("Image/Path").text
        assert "/" not in path
        assert path == "CD3.tif"

    def test_image_count_matches_records(self):
        records = self._records(["A", "B", "C", "D"])
        root = build_xml("TEST", 0, records)
        assert len(root.findall("Image")) == 4
