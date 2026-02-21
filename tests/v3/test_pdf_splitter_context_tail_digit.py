"""Tests for context correction on trailing-digit OCR errors."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.output_organizer import OutputOrganizer
from v3.components.pdf_splitter import PdfSplitter
from v3.utils.config_manager import ConfigManager


def _splitter() -> PdfSplitter:
    config = ConfigManager.load_from_file("v3/config.ini")
    validator = HeaderValidator(config)
    organizer = OutputOrganizer("output")
    return PdfSplitter(config, validator, organizer)


def test_context_correction_merges_tail_digit_variant():
    splitter = _splitter()
    groups = [
        (31, 32, "B-E-UUY-R4092527"),
        (33, 33, "B-E-UUY-R40925274"),
        (34, 34, "B-E-UUY-R4092527"),
    ]
    corrected = splitter._apply_context_correction(groups)
    assert corrected == [(31, 34, "B-E-UUY-R4092527")]


def test_context_correction_does_not_merge_different_last_digit():
    splitter = _splitter()
    groups = [
        (7, 8, "B-E-UUY-R4092558"),
        (9, 10, "B-E-UUY-R4092528"),
    ]
    corrected = splitter._apply_context_correction(groups)
    assert corrected == groups
