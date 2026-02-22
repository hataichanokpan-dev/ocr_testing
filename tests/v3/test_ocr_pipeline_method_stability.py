"""Tests for OCR method-level stability and early-exit behavior."""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager
from v3.utils.ocr_context import OCRContext


def _pipeline_stub() -> OCRPipeline:
    pipeline = OCRPipeline.__new__(OCRPipeline)
    pipeline.config = ConfigManager.load_from_file("v3/config.ini")
    pipeline.validator = HeaderValidator(pipeline.config)
    pipeline._tesseract_available = True
    pipeline._get_tesseract_configs = lambda: [(7, "--psm 7 --oem 3")]
    return pipeline


def test_run_ocr_methods_waits_for_repeated_strong_result():
    pipeline = _pipeline_stub()
    pipeline.config.max_ocr_attempts = 4
    pipeline.config.early_exit_score = 90
    pipeline.config.tesseract_confidence_threshold = 82.0
    pipeline.config.ocr_method_early_exit_min_attempts = 2
    pipeline.config.ocr_method_early_exit_min_confirmations = 2

    # First method is wrong but still "excellent"; next two agree on the correct value.
    pipeline._method2_threshold = lambda _gray, _cfg, _ctx: ("B-TW-UEL-S18011737", 202, 95.0)
    pipeline._method3_adaptive = lambda _gray, _cfg, _ctx: ("B-TW-UEI-S18011757", 202, 95.0)
    pipeline._method4_otsu = lambda _gray, _cfg, _ctx: ("B-TW-UEI-S18011757", 202, 95.0)
    pipeline._method5_bilateral = lambda _gray, _cfg, _ctx: ("", -1, 0.0)

    img = Image.new("RGB", (64, 24), color="white")
    context = OCRContext(filename="dummy.pdf", page_num=1, job_id="t1")
    best_text, method_results, _freq = pipeline._run_ocr_methods(img, context)

    assert best_text == "B-TW-UEI-S18011757"
    non_empty = [v for v in method_results.values() if isinstance(v, dict) and str(v.get("text", "")).strip()]
    assert len(non_empty) >= 3


def test_count_non_empty_method_results_ignores_meta():
    method_results = {
        "method2_psm7": {"text": "B-TW-UEI-S18011757"},
        "method3_psm7": {"text": ""},
        "__meta__": {"glyph_disambiguation_reason": "classifier_no_change(no_votes=1)"},
    }
    assert OCRPipeline._count_non_empty_method_results(method_results) == 1
