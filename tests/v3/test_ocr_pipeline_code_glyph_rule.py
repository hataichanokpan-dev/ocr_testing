"""Tests for width-based code 0/O disambiguation rule."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager


def _pipeline_stub() -> OCRPipeline:
    pipeline = OCRPipeline.__new__(OCRPipeline)
    pipeline.config = ConfigManager.load_from_file("v3/config.ini")
    return pipeline


def test_apply_code_zero_width_rule_converts_wider_internal_zero():
    pipeline = _pipeline_stub()
    header = "B-FD-020H-S18020267"
    widths = {5: 10.0, 7: 13.0}

    refined, reason = pipeline._apply_code_zero_width_rule(header, 2, widths)
    assert refined == "B-FD-02OH-S18020267"
    assert "width_ratio" in reason


def test_apply_code_zero_width_rule_keeps_when_no_outlier():
    pipeline = _pipeline_stub()
    header = "B-FD-020H-S18020267"
    widths = {5: 10.0, 7: 10.5}

    refined, reason = pipeline._apply_code_zero_width_rule(header, 2, widths)
    assert refined == header
    assert reason == "no_width_outlier"
