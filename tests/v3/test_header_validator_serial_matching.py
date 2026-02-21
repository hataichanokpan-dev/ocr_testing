"""Regression tests for serial-based header matching."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.utils.config_manager import ConfigManager


def _validator() -> HeaderValidator:
    config = ConfigManager.load_from_file("v3/config.ini")
    return HeaderValidator(config)


def test_non_strict_serials_with_one_digit_difference_do_not_merge():
    validator = _validator()
    h1 = "B-E-UUY-R4092558"
    h2 = "B-E-UUY-R4092528"
    assert validator.headers_match(h1, h2, 0.85) is False


def test_strict_plus_nearby_non_strict_can_merge_for_ocr_drift():
    validator = _validator()
    h1 = "B-HK-ZN1-S179780077"
    h2 = "B-HK-ZN1-S17978007"
    assert validator.headers_match(h1, h2, 0.85) is True


def test_identical_non_strict_serials_still_match():
    validator = _validator()
    h1 = "B-E-UUY-R4092533"
    h2 = "B-E-UUY-R4092533"
    assert validator.headers_match(h1, h2, 0.85) is True
