"""Direct smoke test for OCRPipeline V3 initialization."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.components.header_validator import HeaderValidator
from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager
from v3.utils.debug_manager import DebugImageManager
from v3.utils.metrics_tracker import MetricsTracker

print("Testing OCRPipeline V3 native OCR setup...")

config = ConfigManager.load_from_file("v3/config.ini")
validator = HeaderValidator(config)
debug_mgr = DebugImageManager("debug_images", True, 30, True)
metrics = MetricsTracker(True)
pipeline = OCRPipeline(config, validator, debug_mgr, metrics)

print(f"OCR enhancer initialized: {pipeline.ocr_enhancer is not None}")
print(f"Paddle fallback enabled: {pipeline._enable_paddleocr_fallback}")
print("Pipeline initialized successfully.")
