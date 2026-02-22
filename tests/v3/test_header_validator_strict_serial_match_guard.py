"""Strict serial guard tests for header matching."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.utils.config_manager import ConfigManager


def _validator() -> HeaderValidator:
    cfg = ConfigManager.load_from_file("v3/config.ini")
    return HeaderValidator(cfg)


def test_strict_headers_with_different_serials_do_not_match():
    v = _validator()
    a = "B-TW-UET-S18010794"
    b = "B-TW-UEI-S18010792"
    assert v.headers_match(a, b, 0.85) is False


def test_strict_headers_same_serial_can_match_on_high_similarity():
    v = _validator()
    a = "B-TW-UET-S18010794"
    b = "B-TW-UEI-S18010794"
    assert v.headers_match(a, b, 0.85) is True
