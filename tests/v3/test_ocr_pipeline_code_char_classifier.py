"""Tests for character-level O/0 refinement in OCR pipeline."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager


class _ClassifierStub:
    def __init__(self, predicted_char: str, accepted: bool = True):
        self.predicted_char = predicted_char
        self.accepted = accepted

    def predict(self, _glyph):
        return {
            "predicted_char": self.predicted_char,
            "confidence": 0.95,
            "margin": 2.10,
            "accepted": self.accepted,
        }


def _pipeline_stub() -> OCRPipeline:
    pipeline = OCRPipeline.__new__(OCRPipeline)
    pipeline.config = ConfigManager.load_from_file("v3/config.ini")
    pipeline.validator = HeaderValidator(pipeline.config)
    pipeline._zero_o_classifier = _ClassifierStub("O", True)
    pipeline._code_pair_map = OCRPipeline._build_bidirectional_pair_map(
        pipeline.config.code_ambiguity_pairs
    )
    return pipeline


def test_char_classifier_refines_internal_zero_to_o():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = True
    pipeline.config.enable_code_glyph_width_fallback = False

    # Header: B-FD-020H-S18020267 -> code starts at index 5, internal zero at index 7.
    pipeline._extract_char_boxes = lambda _text, _img: {7: (1, 1, 8, 8)}
    pipeline._crop_char = lambda _img, _box: object()
    pipeline._predict_pair_tesseract_votes = (
        lambda _glyph, _pair: ({"O": 2, "0": 0}, ["ocr=O@91.0"])
    )

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-FD-020H-S18020267",
        object(),
        evidence_headers=[
            "B-FD-02OH-S18020267",
            "B-FD-02OH-S18020267",
            "B-FD-020H-S18020267",
        ],
    )

    assert refined == "B-FD-02OH-S18020267"
    assert "classifier(" in reason


def test_char_classifier_requires_min_vote_support():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = False
    pipeline.config.enable_code_glyph_width_fallback = False
    pipeline.config.code_char_classifier_min_vote_support = 2

    pipeline._extract_char_boxes = lambda _text, _img: {7: (1, 1, 8, 8)}
    pipeline._crop_char = lambda _img, _box: object()
    pipeline._predict_pair_tesseract_votes = (
        lambda _glyph, _pair: ({"O": 1, "0": 0}, ["ocr=O@80.0"])
    )

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-FD-020H-S18020267",
        object(),
    )

    assert refined == "B-FD-020H-S18020267"
    assert reason.startswith("classifier_no_change")


def test_char_classifier_does_not_flip_leading_zero():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = True
    pipeline.config.enable_code_glyph_width_fallback = False
    pipeline.config.code_char_classifier_allow_leading_zero_to_o = False

    # Only leading zero has box evidence; it must remain numeric.
    pipeline._extract_char_boxes = lambda _text, _img: {5: (1, 1, 8, 8)}
    pipeline._crop_char = lambda _img, _box: object()
    pipeline._predict_pair_tesseract_votes = lambda _glyph, _pair: ({}, [])

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-FD-020H-S18020267",
        object(),
    )

    assert refined == "B-FD-020H-S18020267"
    assert reason.startswith("classifier_no_change")


def test_char_classifier_falls_back_to_width_rule_when_no_boxes():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = True
    pipeline.config.enable_code_glyph_width_fallback = True

    pipeline._extract_char_boxes = lambda _text, _img: {}
    pipeline._refine_code_zero_o_with_glyph_width = lambda _text, _img: (
        "B-FD-02OH-S18020267",
        "width_ratio>=1.12",
    )

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-FD-020H-S18020267",
        object(),
    )

    assert refined == "B-FD-02OH-S18020267"
    assert "width_ratio" in reason


def test_char_classifier_handles_uei_uel_pair():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = False
    pipeline.config.enable_code_glyph_width_fallback = False
    pipeline.config.code_ambiguity_pairs = "O:0,I:L"
    pipeline._code_pair_map = OCRPipeline._build_bidirectional_pair_map(
        pipeline.config.code_ambiguity_pairs
    )

    # In UEL, the last char L should become I when pair-vote supports I.
    pipeline._extract_char_boxes = lambda _text, _img: {7: (1, 1, 8, 8)}
    pipeline._crop_char = lambda _img, _box: object()
    pipeline._predict_pair_tesseract_votes = lambda _glyph, _pair: ({"I": 2, "L": 0}, ["ocr=I@92.0"])

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-TW-UEL-S18011737",
        object(),
    )

    assert refined == "B-TW-UEI-S18011737"
    assert "classifier(" in reason


def test_image_support_rescue_resolves_uei_uel_when_classifier_no_change():
    pipeline = _pipeline_stub()
    pipeline.config.enable_code_char_classifier = False
    pipeline.config.enable_code_glyph_width_fallback = False
    pipeline.config.enable_code_image_support_rescue = True
    pipeline.config.code_ambiguity_pairs = "O:0,I:L"
    pipeline._code_pair_map = OCRPipeline._build_bidirectional_pair_map(
        pipeline.config.code_ambiguity_pairs
    )

    pipeline._extract_char_boxes = lambda _text, _img: {7: (1, 1, 8, 8)}
    pipeline._crop_char = lambda _img, _box: object()
    pipeline._predict_pair_tesseract_votes = lambda _glyph, _pair: ({}, [])
    pipeline._collect_ambiguity_support_candidates = (
        lambda _img: ["B-TW-UEI-S18011737", "B-TW-UEL-S18011737"]
    )

    refined, reason = pipeline._refine_code_zero_o_with_char_classifier(
        "B-TW-UEL-S18011737",
        object(),
    )

    assert refined == "B-TW-UEI-S18011737"
    assert reason.startswith("image_support(")
