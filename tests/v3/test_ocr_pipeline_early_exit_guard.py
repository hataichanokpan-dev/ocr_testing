"""Tests for OCR early-exit suspicious-header guard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager


def _pipeline_stub() -> OCRPipeline:
    pipeline = OCRPipeline.__new__(OCRPipeline)
    pipeline.config = ConfigManager.load_from_file("v3/config.ini")
    pipeline.validator = HeaderValidator(pipeline.config)
    return pipeline


def test_early_exit_guard_flags_country_len_out_of_range():
    pipeline = _pipeline_stub()
    suspicious, reason = pipeline._is_suspicious_for_early_exit("B-CHK-WEE-S17991790")
    assert suspicious is True
    assert "country_len" in reason


def test_early_exit_guard_accepts_normal_country():
    pipeline = _pipeline_stub()
    suspicious, reason = pipeline._is_suspicious_for_early_exit("B-HK-WFE-S17991790")
    assert suspicious is False
    assert reason == ""
