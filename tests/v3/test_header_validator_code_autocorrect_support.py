"""Tests for support-based code ambiguity resolution."""

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


def test_resolve_code_ambiguity_applies_when_alternative_supported():
    validator = _validator()
    base = "B-FD-020H-S18020267"
    candidates = [
        "B-FD-020H-S18020267",
        "B-FD-02OH-S18020267",
        "B-FD-02OH-S18020267",
    ]
    resolved, meta = validator.resolve_code_ambiguity_by_support(base, candidates, min_support=1)
    assert resolved == "B-FD-02OH-S18020267"
    assert meta["applied"] is True


def test_resolve_code_ambiguity_skips_without_min_support():
    validator = _validator()
    base = "B-FD-020H-S18020267"
    candidates = [
        "B-FD-020H-S18020267",
        "B-FD-02OH-S18020267",
    ]
    resolved, meta = validator.resolve_code_ambiguity_by_support(base, candidates, min_support=2)
    assert resolved == base
    assert meta["applied"] is False
