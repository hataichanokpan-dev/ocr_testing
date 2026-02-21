# OCR Picklist (V3)

Production entrypoint:

`python v3/pdf_watcher_v3.py`

This repository is now organized as a V3-first project. Legacy V1/V2 files are archived under `legacy/` to keep daily operations clean.

## Active Structure

```text
v3/                 # Active application code and service scripts
tests/v3/           # Active V3 tests and checks
input/              # Incoming PDFs
output/             # Split/renamed output PDFs
reports/            # Extraction reports
logs/               # Runtime logs
debug_images/       # OCR debug images
legacy/             # Archived V1/V2 scripts and historical docs
```

## Quick Start

1. Install dependencies:
   `pip install -r requirements.txt`
2. Configure:
   `v3/config.ini`
3. Run watcher:
   `python v3/pdf_watcher_v3.py`

## Service Mode (Windows)

Use scripts in `v3/`:

- `v3/install_service_v3.bat`
- `v3/uninstall_service_v3.bat`

