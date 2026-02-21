# OCR Picklist V3

Production-ready PDF header extraction and split pipeline for factory picklist workflows.

The active runtime entrypoint is:

```powershell
python v3/pdf_watcher_v3.py
```

This project is optimized for **CPU-only deployments** with optional OCR fallback strategies for hard pages.

## Table of Contents

1. [What This Service Does](#what-this-service-does)
2. [System Architecture](#system-architecture)
3. [OCR Reading Principles (Deep Dive)](#ocr-reading-principles-deep-dive)
4. [Header Validation and Confidence Model](#header-validation-and-confidence-model)
5. [PDF Grouping and Splitting Logic](#pdf-grouping-and-splitting-logic)
6. [Output, Reports, and Metrics](#output-reports-and-metrics)
7. [Installation](#installation)
8. [Configuration Reference](#configuration-reference)
9. [Run Modes](#run-modes)
10. [Troubleshooting](#troubleshooting)
11. [Performance and Accuracy Tuning](#performance-and-accuracy-tuning)
12. [Repository Layout](#repository-layout)

## What This Service Does

For each incoming PDF in `input/`, the system:

1. Reads every configured page.
2. Extracts header text from a fixed ROI (region of interest).
3. Normalizes and validates extracted headers.
4. Groups contiguous pages that belong to the same header.
5. Writes split PDF files into date-organized output folders.
6. Produces extraction/error reports and operational metrics.

Main outputs:

- Split files: `output/YYYY/YYYY-MM-DD/*.pdf`
- Reports: `reports/YYYY-MM-DD/*.xlsx`
- Logs: `logs/*.log`
- Runtime metrics: `metrics.json`
- Daily metrics snapshots: `daily/performance_metrics_YYYYMMDD.json`

## System Architecture

```text
input/*.pdf
   |
   v
v3/pdf_watcher_v3.py
   |
   v
v3/pdf_extractor_v3.py
   |-- ROI + direct text attempt
   |-- OCR pipeline (adaptive rendering + multi-method voting)
   |-- header validator (normalization + structural scoring + strict serial gate)
   |-- pdf splitter (grouping + context correction + atomic file write)
   |-- csv reporter / api logger / metrics tracker
   v
output + reports + daily metrics
```

Core modules:

- `v3/pdf_watcher_v3.py`: folder watcher service.
- `v3/pdf_extractor_v3.py`: orchestration layer per PDF/job.
- `v3/components/ocr_pipeline.py`: multi-scale OCR strategy and candidate selection.
- `v3/components/header_validator.py`: normalization, scoring, strict serial checks, header matching.
- `v3/components/pdf_splitter.py`: page grouping, context correction, split file creation.
- `v3/utils/metrics_tracker.py`: job/page timing and daily summary export.

## OCR Reading Principles (Deep Dive)

This pipeline is designed to reduce two common OCR failure classes:

- **character confusion** (e.g., `S` vs `8`, `O` vs `0`, missing `-`)
- **false confidence** (wrong text but high OCR confidence)

### 1) ROI-first extraction

Header OCR runs only inside a configured rectangle:

- `header_area_top`
- `header_area_left`
- `header_area_width`
- `header_area_height`

Why this matters:

- removes noisy text from body area
- improves OCR speed
- improves stability of scoring and grouping

### 2) Direct text before OCR

The extractor first attempts PDF text-layer extraction from ROI:

- If extracted text is **strict-valid**, it is accepted immediately.
- If not strict-valid, pipeline falls back to image OCR.

This avoids expensive OCR when text-layer data is trustworthy, while rejecting weak direct text.

### 3) Adaptive rendering strategy

For scanned pages, OCR renders ROI at multiple scales:

1. `initial_render_scale` (fast path)
2. `3.0x`
3. `max_render_scale` (accuracy path)

Escalation is score-driven. Early exit occurs only when candidate is strong **and strict-valid**.

### 4) Multi-method OCR per scale

Per rendered image, pipeline runs several preprocessing + Tesseract method variants:

- thresholding
- adaptive thresholding
- Otsu
- bilateral filtering
- multi-PSM configs (`7`, `6`, `13` deduplicated)

Each candidate captures:

- OCR text
- validator score
- OCR confidence
- strict-valid flag

### 5) Candidate voting and selection

Final candidate ranking is weighted by:

- validator score
- OCR confidence
- repeat frequency across methods
- strict-valid bonus

Strict-valid candidates are prioritized in ranking and early-exit logic.

### 6) Optional fallback engine

If enabled, PaddleOCR fallback can run when native OCR is weak.

- Works on CPU (no GPU required).
- Can be used with ensemble voting.
- Should be reserved for low-confidence pages to control latency.

## Header Validation and Confidence Model

`v3/components/header_validator.py` enforces quality gates that are separate from OCR engine confidence.

### Normalization

- uppercase conversion
- whitespace collapse
- allowed character filtering
- separator cleanup
- serial ambiguity normalization (config-driven map)

### Structural checks

Supports secure/flexible document forms:

- `prefix-country-code-serial`
- `prefix-code-serial`
- `prefix-country-serial`

### Strict serial gate

Key controls from `v3/config.ini`:

- `serial_prefix_required = true`
- `serial_digits_exact = 8`
- `pattern_serial_allowed_prefixes = S,R`
- `invalid_serial_score_cap = 89`

Effect:

- values like `...-S179780077` (extra digit) are score-capped
- values like `...-817976332` (missing prefix) are score-capped
- invalid serial cannot become high-confidence winner

### Matching behavior

Header matching is used only for **contiguous page grouping**.

- strict-valid different headers are protected from over-aggressive context merge
- close serial variants can still be treated as OCR noise when one side is weak

## PDF Grouping and Splitting Logic

Grouping is done in `v3/components/pdf_splitter.py`.

### Stage A: contiguous grouping

Pages are scanned sequentially and grouped while headers match.

### Stage B: context correction (single-page outlier fix)

After first-pass grouping, conservative correction runs:

- detects 1-page outlier groups
- compares with previous and next neighbors
- merges into stronger neighbor only when likely OCR error
- never collapses two different strict-valid headers

This targets log patterns like:

- one-page `S179780077` between valid pages of `S17978007`
- one-page malformed serial between long valid run

### Stage C: best-header selection per group

Group label is selected by normalized header voting:

- highest frequency in group
- then strict-valid flag
- then best score

This reduces tie errors where lexicographic ordering previously won by accident.

### Stage D: robust file write

Split output writing uses atomic and fallback strategy:

- write to temp file in output directory
- `os.replace()` to final target
- retry on lock conditions
- regenerate subset if temp file disappears unexpectedly
- fallback unique filename for locked targets

## Output, Reports, and Metrics

### Reports

For each processed PDF:

- extraction report (`extraction_report_*.xlsx`)
- error report (`errors_extraction_report_*.xlsx`) when low confidence/errors exist

### Runtime metrics

`metrics.json` contains rolling summary and recent jobs.

Daily file export is automatic:

- `daily/performance_metrics_YYYYMMDD.json`

### Key KPIs

- `total_pages_processed`
- `avg_processing_time_seconds` (per job)
- `avg_processing_per_page_seconds` (per page)
- OCR and API success rates
- fastest/slowest job duration

Console summary includes:

- `PERFORMANCE METRICS SUMMARY`
- average processing per job and per page

## Installation

### 1) Python dependencies

```powershell
pip install -r requirements.txt
```

### 2) Tesseract OCR

Install Tesseract and configure one of:

- `tesseract_cmd` in `v3/config.ini`
- environment variable `TESSERACT_CMD`
- system PATH

Example:

```ini
tesseract_cmd = C:/Program Files/Tesseract-OCR/tesseract.exe
```

## Configuration Reference

Primary config file: `v3/config.ini`

### OCR controls

- `adaptive_rendering`
- `initial_render_scale`
- `max_render_scale`
- `max_ocr_attempts`
- `early_exit_score`
- `score_threshold_for_escalation`
- `tesseract_psm_mode`
- `tesseract_char_whitelist`

### Validation controls

- `enable_pattern_check`
- `header_pattern`
- `pattern_serial_allowed_prefixes`
- `serial_prefix_required`
- `serial_digits_exact`
- `invalid_serial_score_cap`
- `serial_close_match_threshold`

### Split and naming

- `enable_pdf_splitting`
- `header_similarity_threshold`
- `enable_serial_based_matching`
- `split_naming_pattern`
- `remove_special_chars`

### Metrics

- `enable_metrics_tracking`
- `metrics_export_path`

## Run Modes

### Watcher mode (service)

```powershell
python v3/pdf_watcher_v3.py
```

### One-shot extractor mode

```powershell
python v3/pdf_extractor_v3.py <path_to_pdf>
```

## Troubleshooting

### Error: Tesseract is not installed or not in PATH

Symptoms:

- OCR methods fail with `tesseract is not installed`

Actions:

1. Install Tesseract.
2. Set `tesseract_cmd` explicitly in `v3/config.ini`.
3. Restart the watcher process.

### Error: Permission denied / cannot remove or replace output PDF

Symptoms:

- split create failure on existing output file

Common cause:

- destination file opened by external process

Current behavior:

- retry replace
- regenerate subset when temp disappears
- save to unique fallback name if target remains locked

Operational advice:

- avoid opening output files during active processing

### Wrong serial variants (extra/missing characters)

Examples:

- `S179780077` (extra digit)
- `817976332` (missing `S`/`R` prefix)

Current protection:

- strict serial validation
- invalid score cap
- context correction for single-page outliers

## Performance and Accuracy Tuning

For CPU-only tuning with target around <= 5 seconds per page, see:

- `ACCURACY_UPDATE_CPU_5S_PER_PAGE.md`

Suggested tuning process:

1. Tune ROI first.
2. Measure `avg_processing_per_page_seconds`.
3. Increase attempts/scales only if needed.
4. Enable fallback only for low-confidence cases.
5. Re-check error report and daily metrics.

## Repository Layout

```text
v3/                         Active V3 implementation
tests/v3/                   Tests and smoke checks
input/                      Incoming PDFs
output/                     Split output PDFs (runtime)
reports/                    Excel reports (runtime)
logs/                       Runtime logs
debug_images/               OCR debug artifacts (runtime)
daily/                      Daily metrics JSON snapshots
legacy/                     Archived old versions
README.md                   Project documentation
```

## Notes

- This repository is configured to ignore runtime artifacts (`.pdf`, `.xlsx`, images, logs) via `.gitignore`.
- Keep production calibration changes in `v3/config.ini` under version control.
- Prefer validating changes on a known benchmark PDF set before deploying.
