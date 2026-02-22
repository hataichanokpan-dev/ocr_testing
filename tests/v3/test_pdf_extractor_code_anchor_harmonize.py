"""Tests for code-anchor harmonization in extractor."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.pdf_extractor_v3 import PDFTextExtractorV3
from v3.components.header_validator import HeaderValidator
from v3.utils.config_manager import ConfigManager


def _extractor_stub() -> PDFTextExtractorV3:
    extractor = PDFTextExtractorV3.__new__(PDFTextExtractorV3)
    extractor.config = ConfigManager.load_from_file("v3/config.ini")
    extractor.validator = HeaderValidator(extractor.config)
    return extractor


def test_anchor_harmonize_default_is_enabled():
    ex = _extractor_stub()
    assert ex.config.enable_code_anchor_harmonize is True


def test_anchor_harmonize_propagates_o_variant_when_glyph_evidence_exists():
    ex = _extractor_stub()
    page_headers = [
        (14, "B-FD-02OH-S18018435"),
        (15, "B-FD-02OH-S18018435"),
        (16, "B-FD-020H-S18018435"),
        (17, "B-FD-020H-S18018435"),
        (18, "B-FD-020H-S18018435"),
    ]
    flags = {
        14: "glyph_disambiguated:width_ratio>=1.12",
        15: "glyph_disambiguated:width_ratio>=1.12",
        16: "code_ambiguity:020H->O20H|02OH",
        17: "code_ambiguity:020H->O20H|02OH",
        18: "code_ambiguity:020H->O20H|02OH",
    }

    updated, updates = ex._harmonize_code_ambiguity_headers(page_headers, flags)
    assert all(header == "B-FD-02OH-S18018435" for _p, header in updated)
    assert 16 in updates and 17 in updates and 18 in updates


def test_anchor_harmonize_keeps_single_variant():
    ex = _extractor_stub()
    page_headers = [
        (0, "B-FD-020H-S18020267"),
        (1, "B-FD-020H-S18020267"),
    ]
    flags = {0: "", 1: ""}

    updated, updates = ex._harmonize_code_ambiguity_headers(page_headers, flags)
    assert updated == page_headers
    assert updates == {}


def test_anchor_harmonize_requires_glyph_evidence():
    ex = _extractor_stub()
    page_headers = [
        (0, "B-FD-020H-S18018435"),
        (1, "B-FD-02OH-S18018435"),
        (2, "B-FD-020H-S18018435"),
    ]
    flags = {
        0: "code_ambiguity:020H->02OH",
        1: "code_ambiguity:02OH->020H",
        2: "code_ambiguity:020H->02OH",
    }

    updated, updates = ex._harmonize_code_ambiguity_headers(page_headers, flags)
    assert updated == page_headers
    assert updates == {}
