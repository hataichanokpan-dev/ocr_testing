"""Serial range validation tests (7-8 digits with S/R prefix)."""

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


def test_r_prefix_7_digits_is_strict_valid():
    validator = _validator()
    assert validator.is_strict_header("B-E-UUY-R4092533") is True


def test_r_prefix_9_digits_is_not_strict_valid():
    validator = _validator()
    assert validator.is_strict_header("B-E-UUY-R409253380") is False
