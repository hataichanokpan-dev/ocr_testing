"""
PDF Splitting Test Script
Tests the PDF splitting functionality with a sample PDF
"""

import os
import sys
from pathlib import Path
from configparser import ConfigParser
from pdf_extractorV2 import PDFTextExtractor

def test_split_pdf(pdf_path, output_folder=None):
    """
    Test PDF splitting functionality
    
    Args:
        pdf_path: Path to input PDF file
        output_folder: Output folder (optional, uses config if None)
    """
    print("=" * 70)
    print("PDF SPLITTING TEST")
    print("=" * 70)
    
    # Load configuration
    config_path = Path(__file__).parent / 'config.ini'
    if not config_path.exists():
        print(f"❌ Error: config.ini not found at {config_path}")
        return False
    
    print(f"✓ Loading config from: {config_path}")
    config = ConfigParser()
    config.read(config_path)
    
    # Check if splitting is enabled
    splitting_enabled = config.getboolean('Settings', 'enable_pdf_splitting', fallback=False)
    print(f"✓ PDF Splitting Enabled: {splitting_enabled}")
    
    if not splitting_enabled:
        print("\n⚠️  WARNING: PDF splitting is disabled in config.ini")
        print("   Set 'enable_pdf_splitting = True' to enable this feature")
        return False
    
    # Check if input file exists
    if not os.path.exists(pdf_path):
        print(f"❌ Error: Input PDF not found at {pdf_path}")
        return False
    
    print(f"✓ Input PDF: {pdf_path}")
    
    # Create extractor
    print("✓ Creating PDFTextExtractor...")
    extractor = PDFTextExtractor(config)
    
    # Perform split
    print("\n" + "=" * 70)
    print("STARTING SPLIT OPERATION")
    print("=" * 70 + "\n")
    
    try:
        split_results = extractor.split_pdf_by_header(pdf_path, output_folder)
        
        print("\n" + "=" * 70)
        print("SPLIT RESULTS")
        print("=" * 70)
        
        if not split_results:
            print("❌ No splits created")
            print("   Possible reasons:")
            print("   - All pages have the same header (only 1 group)")
            print("   - Headers could not be extracted")
            print("   - min_pages_per_split threshold not met")
            return False
        
        print(f"✓ Successfully created {len(split_results)} split file(s)\n")
        
        total_size = 0
        for i, (output_path, header_text, page_range) in enumerate(split_results, 1):
            file_size = os.path.getsize(output_path)
            total_size += file_size
            
            print(f"{i}. {Path(output_path).name}")
            print(f"   Header: {header_text}")
            print(f"   Pages:  {page_range}")
            print(f"   Size:   {file_size:,} bytes")
            print(f"   Path:   {output_path}")
            print()
        
        print(f"Total output size: {total_size:,} bytes")
        print(f"Original size:     {os.path.getsize(pdf_path):,} bytes")
        
        print("\n" + "=" * 70)
        print("✓ TEST PASSED")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during split operation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("\nPDF Splitting Test Script")
    print("-" * 70)
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("\nUsage:")
        print(f"  python {Path(__file__).name} <input_pdf> [output_folder]")
        print("\nExample:")
        print(f"  python {Path(__file__).name} test_input/document.pdf")
        print(f"  python {Path(__file__).name} test_input/document.pdf test_output/splits")
        print("\nTest with sample:")
        
        # Try to find a sample PDF in test_input folder
        test_input = Path(__file__).parent / 'test_input'
        if test_input.exists():
            pdf_files = list(test_input.glob('*.pdf'))
            if pdf_files:
                sample_pdf = pdf_files[0]
                print(f"  python {Path(__file__).name} {sample_pdf}")
            else:
                print(f"  (No PDF files found in {test_input})")
        
        return 1
    
    # Get arguments
    input_pdf = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run test
    success = test_split_pdf(input_pdf, output_folder)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
