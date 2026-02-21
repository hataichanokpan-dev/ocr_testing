"""Unit tests for cross-scale OCR voting behavior."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.ocr_pipeline import OCRPipeline


def test_cross_scale_vote_prefers_repeated_candidate():
    candidates = [
        {
            "text": "B-E-UUY-R4092533EE",
            "score": 89,
            "strict_valid": False,
            "freq_ratio": 0.50,
            "method_results": {},
            "scale": 2.0,
        },
        {
            "text": "B-E-UUY-R4092533",
            "score": 89,
            "strict_valid": False,
            "freq_ratio": 0.50,
            "method_results": {},
            "scale": 3.0,
        },
        {
            "text": "B-E-UUY-R4092533",
            "score": 89,
            "strict_valid": False,
            "freq_ratio": 0.75,
            "method_results": {},
            "scale": 6.0,
        },
    ]

    picked = OCRPipeline._select_cross_scale_result(candidates)
    assert picked["text"] == "B-E-UUY-R4092533"


def test_cross_scale_vote_prefers_strict_valid_candidate():
    candidates = [
        {
            "text": "B-HK-ZN1-S179780077",
            "score": 89,
            "strict_valid": False,
            "freq_ratio": 0.90,
            "method_results": {},
            "scale": 2.0,
        },
        {
            "text": "B-HK-ZN1-S17978007",
            "score": 202,
            "strict_valid": True,
            "freq_ratio": 0.40,
            "method_results": {},
            "scale": 3.0,
        },
    ]

    picked = OCRPipeline._select_cross_scale_result(candidates)
    assert picked["text"] == "B-HK-ZN1-S17978007"
