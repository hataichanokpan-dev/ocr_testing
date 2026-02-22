"""Quick test for V3 OCR processing"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.pdf_extractor_v3 import PDFTextExtractorV3
from v3.utils.config_manager import ConfigManager

# Load config
config = ConfigManager.load_from_file('v3/config.ini')

# Create extractor
extractor = PDFTextExtractorV3(config)

# Process PDF (use absolute path from output folder)
pdf_path = Path('output/2026/2026-02-05/B_C_5U5_R4091534_pages_1-2.pdf').absolute()
if not pdf_path.exists():
    pdf_path = Path('input').absolute()
    if pdf_path.exists():
        pdfs = list(pdf_path.glob('*.pdf'))
        if pdfs:
            pdf_path = pdfs[0]
        else:
            print("No PDF found in input folder")
            exit(1)
    else:
        print(f"PDF not found: {pdf_path}")
        exit(1)

print(f"Testing with: {pdf_path}")
result = extractor.process_pdf(str(pdf_path))

# Print result
print(f"\n{'='*60}")
print(f"RESULT:")
print(f"  Headers extracted: {result.get('headers_extracted', 0)}")
print(f"  Split PDFs: {result.get('split_pdfs_created', 0)}")
print(f"  Processing time: {result.get('metrics', {}).get('processing_time_seconds', 0):.2f}s")

print(f"{'='*60}\n")

# Cleanup
extractor.shutdown()
