# PDF Splitting Feature Guide

## Overview
The PDF splitting feature allows you to automatically split a single PDF file into multiple PDF files based on changes in the header text. Pages with the same header will be grouped together in one file, and when the header changes, a new file is created.

## How It Works

### Workflow
```
Single PDF Input
    ↓
Read headers from all pages
    ↓
Detect when header text changes
    ↓
Group consecutive pages with same header
    ↓
Create separate PDF for each group
    ↓
Multiple PDF Output (named by header text)
```

### Example Scenario
**Input PDF (10 pages):**
- Pages 1-3: Header = "B-C-5U5-R4091534"
- Pages 4-7: Header = "P-F-W1A-S17995875"
- Pages 8-10: Header = "B-C-5U5-R4091534"

**Output (3 PDFs):**
1. `B-C-5U5-R4091534_pages_1-3.pdf` (pages 1-3)
2. `P-F-W1A-S17995875_pages_4-7.pdf` (pages 4-7)
3. `B-C-5U5-R4091534_pages_8-10.pdf` (pages 8-10)

Note: Even though pages 1-3 and 8-10 have the same header, they create separate files because they're not consecutive.

## Configuration

### Enable PDF Splitting
Open `config.ini` and set:
```ini
enable_pdf_splitting = True
```

### Configuration Options

#### Basic Settings
```ini
[Settings]
# Enable/disable splitting feature
enable_pdf_splitting = False

# Output folder for split files (leave empty to use output_folder)
split_output_folder = D:\output\splits

# Minimum pages per split (avoid very small PDFs)
min_pages_per_split = 1

# Delete original PDF after successful splitting
delete_original_after_split = False
```

#### Filename Pattern
Control how split files are named:
```ini
# Available placeholders:
# {header}   = Extracted header text (sanitized)
# {start}    = First page number (1-based)
# {end}      = Last page number (1-based)
# {index}    = Split index (1, 2, 3...)
# {original} = Original PDF filename (without extension)

split_naming_pattern = {header}_pages_{start}-{end}
```

**Pattern Examples:**
| Pattern | Output Example |
|---------|---------------|
| `{header}_pages_{start}-{end}` | `B-C-5U5-R4091534_pages_1-3.pdf` |
| `{original}_split_{index}_{header}` | `document_split_1_B-C-5U5-R4091534.pdf` |
| `{index}_{header}` | `1_B-C-5U5-R4091534.pdf` |
| `{header}` | `B-C-5U5-R4091534.pdf` (may create duplicates!) |

#### Header Similarity Threshold
Control how strict header matching is:
```ini
# 1.0 = Exact match only (default)
# 0.9 = 90% similarity acceptable (useful if OCR varies slightly)
header_similarity_threshold = 1.0
```

**Example:**
- `threshold = 1.0`: "B-C-5U5-R4091534" ≠ "B-C-5U5-R4091534 " (different)
- `threshold = 0.95`: "B-C-5U5-R4091534" ≈ "B-C-5U5-R4091534 " (similar enough)

## Usage

### Method 1: Automatic (File Watcher)
1. Configure settings in `config.ini`
2. Run the watcher: `python pdf_watcher.py`
3. Drop PDF files into the watch folder
4. Split files appear in the output folder automatically

### Method 2: Manual (Python API)
```python
from configparser import ConfigParser
from pdf_extractorV2 import PDFTextExtractor

# Load config
config = ConfigParser()
config.read('config.ini')

# Create extractor
extractor = PDFTextExtractor(config)

# Split PDF
split_results = extractor.split_pdf_by_header(
    pdf_path='path/to/input.pdf',
    output_folder='path/to/output'
)

# Process results
for output_path, header_text, page_range in split_results:
    print(f"Created: {output_path}")
    print(f"  Header: {header_text}")
    print(f"  Pages: {page_range}")
```

## Output

### Split Files
Each split PDF contains:
- Only pages with the same header text
- Original page content and formatting
- Metadata from original PDF

### Naming
Files are automatically named using:
1. Extracted header text (sanitized for filesystem)
2. Pattern placeholders (start, end, index, etc.)
3. Auto-incremented counter if filename exists (e.g., `_1`, `_2`)

### Folder Structure
```
output_folder/
├── B-C-5U5-R4091534_pages_1-3.pdf
├── P-F-W1A-S17995875_pages_4-7.pdf
└── B-C-5U5-R4091534_pages_8-10.pdf
```

## API Logging

If `enable_api_logging = True`, split operations are logged to the API with:
- Original filename
- Number of splits created
- Header text for each split
- Page ranges for each split
- Timestamp

**Payload Example:**
```json
{
  "timestamp": "2026-01-28 14:30:22",
  "original_filename": "document.pdf",
  "operation": "pdf_split",
  "split_count": 3,
  "splits": "[{\"filename\":\"B-C-5U5-R4091534_pages_1-3.pdf\",\"header\":\"B-C-5U5-R4091534\",\"pages\":\"1-3\"},...]",
  "status": "success"
}
```

## Troubleshooting

### Issue: No splits created
**Causes:**
- All pages have the same header (only 1 group)
- Headers couldn't be extracted (OCR failed)
- `min_pages_per_split` too high

**Solutions:**
- Check debug images in `debug_images/` folder
- Lower `min_pages_per_split` to 1
- Verify header area coordinates
- Enable `save_debug_images = True` to see what's being extracted

### Issue: Too many small splits
**Causes:**
- Header text varies slightly between pages (OCR noise)
- Headers genuinely change frequently

**Solutions:**
- Increase `header_similarity_threshold` to 0.9 or 0.95
- Increase `min_pages_per_split` to merge small groups
- Review debug logs to see header variations

### Issue: Wrong header detection
**Causes:**
- Header area coordinates incorrect
- OCR struggling with text quality

**Solutions:**
- Adjust header area in config: `header_area_top`, `header_area_left`, `header_area_width`, `header_area_height`
- Check `save_debug_images = True` to see extracted region
- Enable `ocr_filter_black_text = True` to ignore colored watermarks

### Issue: Duplicate filenames
**Causes:**
- Same header appears in non-consecutive pages
- Naming pattern doesn't include unique identifier

**Solutions:**
- Use pattern with page ranges: `{header}_pages_{start}-{end}`
- Include index: `{header}_split_{index}`
- System auto-appends `_1`, `_2` etc. to avoid overwrites

## Advanced Configuration

### Split to Different Folder
```ini
# Keep standard renames in one folder, splits in another
output_folder = D:\output\renamed
split_output_folder = D:\output\splits
```

### Disable Standard Rename, Enable Only Splitting
```ini
# This processes files only when splitting is enabled
# When disabled, files are not processed
enable_pdf_splitting = True
```

### Combine with Timestamp
```ini
# Original file gets renamed with timestamp
add_timestamp = True
# Split files use header-based names
enable_pdf_splitting = True
```

## Performance Considerations

### Large PDFs
- Splitting is fast (just copying page references, not re-rendering)
- Header extraction uses same optimized OCR as standard processing
- Parallel processing enabled by default (`enable_parallel_processing = True`)

### Memory Usage
- Original PDF is kept in memory during splitting
- Very large PDFs (>100MB) may use significant RAM
- One PDF is processed at a time (no concurrent splitting)

### Processing Time
For a 50-page PDF:
- Header extraction: ~2-5 seconds per page (with OCR)
- Split creation: <1 second per split
- Total: ~2-3 minutes for 50 pages with 5 splits

## Example Configurations

### Configuration 1: Simple Split
```ini
enable_pdf_splitting = True
split_output_folder = D:\splits
split_naming_pattern = {header}
min_pages_per_split = 1
header_similarity_threshold = 1.0
delete_original_after_split = True
```

### Configuration 2: Detailed Split with Page Ranges
```ini
enable_pdf_splitting = True
split_output_folder = D:\output\by_header
split_naming_pattern = {original}_part{index}_{header}_pages{start}-{end}
min_pages_per_split = 2
header_similarity_threshold = 0.95
delete_original_after_split = False
```

### Configuration 3: Fuzzy Matching for Noisy OCR
```ini
enable_pdf_splitting = True
split_output_folder = 
split_naming_pattern = {header}_pages_{start}-{end}
min_pages_per_split = 1
header_similarity_threshold = 0.9
delete_original_after_split = False
ocr_filter_black_text = True
```

## Best Practices

1. **Test First**: Try with a sample PDF before processing important documents
2. **Check Debug Images**: Enable `save_debug_images = True` to verify header extraction
3. **Use Page Ranges**: Include `{start}-{end}` in naming pattern for clarity
4. **Keep Originals**: Set `delete_original_after_split = False` until confident
5. **Monitor Logs**: Check `pdf_watcher.log` for detailed processing info
6. **Adjust Threshold**: If OCR varies, increase `header_similarity_threshold` to 0.9-0.95

## Comparison: Standard vs. Splitting Mode

| Feature | Standard Mode | Splitting Mode |
|---------|--------------|----------------|
| Input | 1 PDF | 1 PDF |
| Output | 1 renamed PDF | Multiple PDFs |
| Header Reading | First page only | All pages |
| Grouping | N/A | By header change |
| Processing Time | ~5 seconds | ~2-5 sec × pages |
| Use Case | Simple rename | Document separation |

## FAQ

**Q: Can I split by something other than header text?**  
A: Currently only header-based splitting is supported. You can adjust the extraction region using `header_area_*` settings.

**Q: What if some pages have no header?**  
A: Pages without headers are treated as empty string headers and grouped separately.

**Q: Can I merge non-consecutive pages with same header?**  
A: No, only consecutive pages are grouped. This is by design to maintain document order.

**Q: Does splitting work with encrypted PDFs?**  
A: No, encrypted PDFs must be decrypted first.

**Q: Can I preview splits before creating them?**  
A: Currently no preview. Check logs for group detection info before actual split.

**Q: Will this work with scanned PDFs?**  
A: Yes! OCR is used automatically if text can't be extracted directly.

## Support

For issues or questions:
1. Check `pdf_watcher.log` for detailed error messages
2. Enable debug images: `save_debug_images = True`
3. Review `API_LOGGING_DOCUMENTATION.md` for API integration
4. Check `PATTERN_VALIDATION.md` for header format validation

---

**Version:** 2.0 (PDF Splitting Feature)  
**Last Updated:** January 28, 2026
