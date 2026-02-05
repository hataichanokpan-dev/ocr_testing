"""Verbose test for V3"""
import logging
from pathlib import Path
from v3.pdf_extractor_v3 import PDFTextExtractorV3
from v3.utils.config_manager import ConfigManager

# Set verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("="*60)
print("VERBOSE TEST")
print("="*60)

# Load config
config = ConfigManager.load_from_file('v3/config.ini')
print(f"Config loaded - pages_to_read: {config.pages_to_read}")

# Create extractor
extractor = PDFTextExtractorV3(config)

# Process PDF
pdf_path = Path('input/20260127064032221.pdf').absolute()
print(f"\nProcessing: {pdf_path}")
print(f"File exists: {pdf_path.exists()}")

result = extractor.process_pdf(str(pdf_path))

print(f"\n{'='*60}")
print(f"RESULT:")
print(f"  Headers: {result.get('headers_extracted', 0)}")
print(f"  Splits: {result.get('split_pdfs_created', 0)}")
print(f"{'='*60}\n")

extractor.shutdown()
