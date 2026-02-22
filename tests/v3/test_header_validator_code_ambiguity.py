"""Tests for observe-only code O/0 ambiguity inspection."""

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


def test_inspect_code_ambiguity_detects_020h():
    validator = _validator()
    info = validator.inspect_code_ambiguity("B-FD-020H-S18020267")

    assert info["enabled"] is True
    assert info["is_ambiguous"] is True
    assert info["code_segment"] == "020H"
    assert "02OH" in info["alternative_codes"]
    assert "B-FD-02OH-S18020267" in info["alternative_headers"]


def test_inspect_code_ambiguity_skips_non_mixed_codes():
    validator = _validator()
    info = validator.inspect_code_ambiguity("B-FD-ABCD-S18020267")

    assert info["is_ambiguous"] is False
