"""Tests for shape fitness and split best-header tie-break."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.output_organizer import OutputOrganizer
from v3.components.pdf_splitter import PdfSplitter
from v3.utils.config_manager import ConfigManager


def _context():
    config = ConfigManager.load_from_file("v3/config.ini")
    validator = HeaderValidator(config)
    splitter = PdfSplitter(config, validator, OutputOrganizer("output"))
    return config, validator, splitter


def test_shape_fitness_prefers_hk_over_chk():
    _config, validator, _splitter = _context()
    hk = "B-HK-WFE-S17991790"
    chk = "B-CHK-WEE-S17991790"
    assert validator.header_shape_fitness(hk) > validator.header_shape_fitness(chk)


def test_splitter_best_header_tie_prefers_shape_fitness():
    _config, _validator, splitter = _context()
    headers = [
        "B-CHK-WEE-S17991790",
        "B-HK-WFE-S17991790",
    ]
    assert splitter._select_best_header(headers) == "B-HK-WFE-S17991790"


def test_splitter_best_header_tie_uses_stable_text_order():
    _config, _validator, splitter = _context()
    headers = [
        "B-TW-UET-S18010794",
        "B-TW-UEI-S18010794",
    ]
    assert splitter._select_best_header(headers) == "B-TW-UEI-S18010794"
