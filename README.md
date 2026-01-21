# PDF Folder Watcher with OCR

Automatically monitors a folder for new PDF files from scanners, extracts text from the header area, and renames files based on the extracted text.

## Features

- 📁 **Folder Monitoring**: Watches a specified folder for new PDF files
- 📄 **Text Extraction**: Extracts text from header area of PDF files
- 🔤 **OCR Support**: Uses Tesseract OCR for scanned PDFs without text layer
- ✏️ **Auto Rename**: Renames files based on extracted header text
- 🔧 **Configurable**: Highly customizable via config file
- 📝 **Logging**: Comprehensive logging for monitoring and debugging

## Requirements

- Python 3.7 or higher
- Tesseract OCR engine

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR

**Windows:**
1. Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (e.g., `tesseract-ocr-w64-setup-5.3.3.20231005.exe`)
3. Add Tesseract to PATH or update the path in your environment

Default installation path: `C:\Program Files\Tesseract-OCR\tesseract.exe`

**If Tesseract is not in PATH, add this to your Python script:**
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## Configuration

Edit `config.ini` to customize the behavior:

```ini
[Settings]
# Folder to watch for new PDF files
watch_folder = C:\Scanned_PDFs

# Folder to save renamed files (leave empty to rename in same folder)
output_folder = 

# Header area to extract text from (as percentage of page)
# Format: top, left, width, height
header_area_top = 0
header_area_left = 0
header_area_width = 100
header_area_height = 15

# File naming options
max_filename_length = 100
remove_special_chars = True
replace_spaces_with = _

# Processing options
delete_original = False
add_timestamp = False
file_extension = .pdf
```

### Configuration Options Explained

- **watch_folder**: The folder to monitor for new PDF files
- **output_folder**: Where to save renamed files (leave empty to use same folder)
- **header_area_***: Define the region to extract text from (0-100 as percentage)
  - `header_area_height = 15` means top 15% of the page
- **max_filename_length**: Maximum characters in filename
- **remove_special_chars**: Remove invalid filename characters
- **replace_spaces_with**: Replace spaces with this character (e.g., _ or -)
- **delete_original**: If True, moves file; if False, copies file
- **add_timestamp**: Append timestamp to filename to avoid duplicates

## Usage

### Start the Watcher

```bash
python pdf_watcher.py
```

The program will:
1. Start monitoring the specified folder
2. Wait for new PDF files
3. Extract text from the header area
4. Rename/copy the file with extracted text
5. Log all activities

### Stop the Watcher

Press `Ctrl+C` to stop the monitoring.

## How It Works

1. **File Detection**: Watches for new `.pdf` files in the target folder
2. **Text Extraction**: 
   - First attempts direct text extraction from PDF
   - Falls back to OCR if PDF is image-based
3. **Filename Generation**: 
   - Sanitizes extracted text
   - Removes invalid characters
   - Truncates to max length
4. **File Processing**:
   - Copies (or moves) file with new name
   - Handles duplicate names automatically
   - Logs all operations

## Example

### Input
- Scanner creates: `scan001.pdf`
- Header text in PDF: "Invoice 2024-123"

### Output
- New file: `Invoice_2024-123.pdf`
- Or with timestamp: `Invoice_2024-123_20240113_143022.pdf`

## Logging

Logs are saved to `pdf_watcher.log` and displayed in console:

```
2024-01-13 14:30:22 - INFO - PDF Folder Watcher Started
2024-01-13 14:30:22 - INFO - Watching folder: C:\Scanned_PDFs
2024-01-13 14:31:05 - INFO - New PDF detected: C:\Scanned_PDFs\scan001.pdf
2024-01-13 14:31:07 - INFO - Extracted text directly: Invoice 2024-123
2024-01-13 14:31:07 - INFO - Copied and renamed: scan001.pdf -> Invoice_2024-123.pdf
```

## Troubleshooting

### Tesseract Not Found
```
Error: Tesseract not found
```
**Solution**: Install Tesseract and ensure it's in PATH, or specify the path in the code.

### No Text Extracted
```
WARNING - No text extracted from: file.pdf
```
**Solution**: 
- Check if header area coordinates are correct
- Verify PDF is not completely empty
- Ensure Tesseract is properly installed for OCR

### Permission Errors
```
Error: Permission denied
```
**Solution**: 
- Ensure the program has read/write access to folders
- Check if files are not locked by another program
- Run with appropriate permissions

## Project Structure

```
OCR_PDW/
├── pdf_watcher.py       # Main application
├── pdf_extractor.py     # PDF text extraction module
├── config.ini           # Configuration file
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── pdf_watcher.log     # Log file (created on run)
```

## Advanced Usage

### Adjust Header Area

To extract from a different area, modify in `config.ini`:

```ini
# Extract from top-right corner (right 50%, top 10%)
header_area_top = 0
header_area_left = 50
header_area_width = 50
header_area_height = 10
```

### Process Existing Files

To process PDFs already in the folder, you can create a batch script:

```python
# process_existing.py
import os
from configparser import ConfigParser
from pdf_extractor import PDFTextExtractor
from pdf_watcher import PDFFileHandler

config = ConfigParser()
config.read('config.ini')

extractor = PDFTextExtractor(config)
handler = PDFFileHandler(config, extractor)

watch_folder = config.get('Settings', 'watch_folder')
for file in os.listdir(watch_folder):
    if file.lower().endswith('.pdf'):
        file_path = os.path.join(watch_folder, file)
        handler.process_pdf(file_path)
```

## License

This project is provided as-is for professional use.

## Support

For issues or questions, check the log file for detailed error messages.
