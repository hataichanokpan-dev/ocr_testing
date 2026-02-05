"""Direct test of OCR pipeline fix"""
import sys
from pathlib import Path

# Force reload
if 'v3' in sys.modules:
    del sys.modules['v3']

# Test the fix directly
from v3.components.ocr_pipeline import OCRPipeline
from v3.utils.config_manager import ConfigManager
from v3.components.header_validator import HeaderValidator
from v3.utils.debug_manager import DebugImageManager
from v3.utils.metrics_tracker import MetricsTracker

print("Testing OCR Pipeline V2 extractor context setup...")

# Load config
config = ConfigManager.load_from_file('v3/config.ini')

# Create components
validator = HeaderValidator(config)
debug_mgr = DebugImageManager('debug_images', True, 30, True)
metrics = MetricsTracker(True)

# Create pipeline
pipeline = OCRPipeline(config, validator, debug_mgr, metrics)

# Check if V2 extractor has the attributes set
print(f"V2 extractor object: {pipeline.v2_extractor}")
print(f"Has _current_debug_filename attr: {hasattr(pipeline.v2_extractor, '_current_debug_filename')}")

# Try setting them
from v3.utils.ocr_context import OCRContext
test_context = OCRContext("test.pdf", 1, 2.0, "test123")

# This should be done in _run_ocr_methods
pipeline.v2_extractor._current_debug_filename = test_context.filename
pipeline.v2_extractor._current_debug_page = test_context.page_num

print(f"After setting:")
print(f"  _current_debug_filename = {pipeline.v2_extractor._current_debug_filename}")
print(f"  _current_debug_page = {pipeline.v2_extractor._current_debug_page}")

print("\n✅ Attribute setting works!")
