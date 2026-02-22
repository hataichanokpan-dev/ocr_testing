"""Tests for ambiguity-tolerant box alignment."""

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
    pipeline._box_alignment_map = OCRPipeline._build_box_alignment_map(
        pipeline.config.code_box_alignment_ambiguity_pairs
    )
    return pipeline


def _boxes_from_text(text: str):
    boxes = []
    x = 0
    for ch in text:
        boxes.append((ch, x, 0, x + 6, 10))
        x += 7
    return boxes


def test_align_char_boxes_tolerates_o0_substitution():
    pipeline = _pipeline_stub()
    target = "B-FD-020H-S18018435"
    ocr_stream = "B-FD-02OH-S18018435"
    aligned = pipeline._align_char_boxes_from_stream(target, _boxes_from_text(ocr_stream))
    assert len(aligned) >= len(target) - 2


def test_align_char_boxes_tolerates_s5_and_fe_substitution():
    pipeline = _pipeline_stub()
    target = "B-FD-SF5-S18018435"
    ocr_stream = "B-FD-5E5-S18018435"
    aligned = pipeline._align_char_boxes_from_stream(target, _boxes_from_text(ocr_stream))
    assert len(aligned) >= len(target) - 2
