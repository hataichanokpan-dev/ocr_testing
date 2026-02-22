"""Tests for anchor-level ambiguity rescue pass."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.pdf_extractor_v3 import PDFTextExtractorV3
from v3.components.header_validator import HeaderValidator
from v3.utils.config_manager import ConfigManager


class _DummyPage:
    class _Rect:
        width = 1000
        height = 1000

    rect = _Rect()


class _DummyPipeline:
    def __init__(self, rescued_header: str):
        self._rescued_header = rescued_header

    def rescue_ambiguous_header(self, page, rect, context, base_header):
        return self._rescued_header, "rescue:test"


def _extractor_stub(rescued_header: str) -> PDFTextExtractorV3:
    extractor = PDFTextExtractorV3.__new__(PDFTextExtractorV3)
    extractor.config = ConfigManager.load_from_file("v3/config.ini")
    extractor.validator = HeaderValidator(extractor.config)
    extractor.ocr_pipeline = _DummyPipeline(rescued_header)
    return extractor


def test_anchor_rescue_updates_all_pages_in_anchor():
    ex = _extractor_stub("B-FD-02OH-S18020267")
    doc = [_DummyPage(), _DummyPage()]
    page_headers = [
        (0, "B-FD-020H-S18020267"),
        (1, "B-FD-020H-S18020267"),
    ]
    flags = {
        0: "glyph_disambiguation_skipped:no_char_boxes;code_ambiguity:020H->02OH",
        1: "glyph_disambiguation_skipped:no_char_boxes;code_ambiguity:020H->02OH",
    }

    updated, updates = ex._rescue_ambiguous_code_anchors(
        doc=doc,
        source_filename="xtest.pdf",
        job_id="job1",
        page_headers=page_headers,
        page_quality_flags=flags,
    )

    assert all(header == "B-FD-02OH-S18020267" for _p, header in updated)
    assert updates == {0: "B-FD-02OH-S18020267", 1: "B-FD-02OH-S18020267"}


def test_anchor_rescue_skips_when_no_nocharboxes_flag():
    ex = _extractor_stub("B-FD-02OH-S18020267")
    doc = [_DummyPage(), _DummyPage()]
    page_headers = [
        (0, "B-FD-020H-S18020267"),
        (1, "B-FD-020H-S18020267"),
    ]
    flags = {
        0: "code_ambiguity:020H->02OH",
        1: "code_ambiguity:020H->02OH",
    }

    updated, updates = ex._rescue_ambiguous_code_anchors(
        doc=doc,
        source_filename="xtest.pdf",
        job_id="job1",
        page_headers=page_headers,
        page_quality_flags=flags,
    )

    assert updated == page_headers
    assert updates == {}
