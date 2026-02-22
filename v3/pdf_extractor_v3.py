"""
PDF Text Extractor V3 - Main Orchestrator
Coordinates all V3 components with improved architecture
"""

import os
import sys
import time
import fitz  # PyMuPDF
import logging
import uuid
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

# Ensure workspace root is on sys.path so `import v3` works when running
# this file directly (e.g. `python v3\pdf_extractor_v3.py`). This inserts
# the parent of the `v3` package directory into `sys.path` before attempting
# to import package-relative modules.
try:
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    # best-effort; if Path or sys isn't available for some reason, imports
    # will proceed and raise normally.
    pass

from v3.utils.config_manager import ExtractionConfig
from v3.utils.ocr_context import OCRContext
from v3.utils.metrics_tracker import MetricsTracker
from v3.utils.debug_manager import DebugImageManager
from v3.components.output_organizer import OutputOrganizer
from v3.components.header_validator import HeaderValidator
from v3.components.ocr_pipeline import OCRPipeline
from v3.components.pdf_splitter import PdfSplitter
from v3.components.extraction_logger import ExtractionLogger
from v3.utils.csv_reporter import CSVReporter

logger = logging.getLogger(__name__)


class PDFTextExtractorV3:
    """
    PDF Text Extractor V3 - Modular Architecture
    
    Improvements over V2:
    - Thread-safe (no shared mutable state)
    - Modular design (separated concerns)
    - Adaptive rendering (2x -> 3x -> 6x)
    - Async API logging (non-blocking)
    - Performance metrics tracking
    - Organized output (Year/Date/Files)
    - Type-safe configuration
    """
    
    def __init__(
        self,
        config: ExtractionConfig,
        metrics_tracker: MetricsTracker = None
    ):
        """
        Initialize PDF Text Extractor V3
        
        Args:
            config: Type-safe extraction configuration
            metrics_tracker: Optional metrics tracker
        """
        self.config = config
        
        # Setup logging level
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        
        # Initialize components
        self.metrics_tracker = metrics_tracker or MetricsTracker(config.enable_metrics_tracking)
        self.debug_manager = DebugImageManager(
            base_folder=config.debug_images_folder,
            organize_by_date=config.organize_by_date,
            retention_days=config.image_retention_days,
            enabled=config.save_debug_images
        )
        self.output_organizer = OutputOrganizer(
            base_output_dir=config.output_base_dir,
            retention_days=config.output_retention_days
        )
        self.validator = HeaderValidator(config)
        self.ocr_pipeline = OCRPipeline(
            config,
            self.validator,
            self.debug_manager,
            self.metrics_tracker
        )
        self.pdf_splitter = PdfSplitter(
            config,
            self.validator,
            self.output_organizer
        )
        
        # Initialize extraction logger
        self.extraction_logger = ExtractionLogger(
            api_url=config.api_log_url,
            enabled=config.enable_api_logging,
            async_mode=config.api_log_async,
            queue_size=config.api_queue_size,
            timeout=config.api_timeout,
            circuit_breaker_threshold=config.circuit_breaker_threshold
        )
        
        # Initialize CSV Reporter (NEW in V3.1)
        self.csv_reporter = CSVReporter(
            output_folder=config.reports_base_dir,
            organize_by_date=config.reports_organize_by_date,
            append_mode=False
        )
        
        logger.info(f"PDFTextExtractorV3 initialized (v3.1.0)")
        logger.info(f"Output structure: {config.output_base_dir}/YYYY/YYYY-MM-DD/files")
        logger.info(f"CSV Reports: reports/YYYY-MM-DD/")
    
    def process_pdf(self, pdf_path: str) -> dict:
        """
        Process a PDF file - extract headers and split
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            dict: Processing result with metrics
        """
        job_id = str(uuid.uuid4())[:8]
        logger.info(f"\n{'='*60}")
        logger.info(f"[JOB {job_id}] Processing: {pdf_path}")
        logger.info(f"{'='*60}")
        
        try:
            # Open PDF
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # Start metrics tracking
            self.metrics_tracker.start_job(
                job_id=job_id,
                filename=Path(pdf_path).name,
                total_pages=total_pages
            )
            
            logger.info(f"[JOB {job_id}] Total pages: {total_pages}")
            
            # Determine which pages to read
            if not self.config.pages_to_read:  # Empty list means 'all'
                pages_to_process = list(range(1, total_pages + 1))
                logger.info(f"[JOB {job_id}] Reading all pages (1-{total_pages})")
            else:
                pages_to_process = self.config.pages_to_read
                logger.info(f"[JOB {job_id}] Reading specified pages: {pages_to_process}")
            
            # Extract headers from specified pages
            page_headers = []
            page_quality_flags = {}
            for page_num in pages_to_process:
                if page_num > total_pages:
                    logger.warning(f"Page {page_num} exceeds total pages ({total_pages})")
                    continue
                
                page = doc[page_num - 1]  # Convert to 0-based
                
                # Extract header from this page
                start_time = time.time()
                header_text, ocr_info = self._extract_header_from_page(
                    page,
                    page_num,
                    Path(pdf_path).name,
                    job_id
                )
                processing_time_ms = (time.time() - start_time) * 1000
                self.metrics_tracker.record_page_processed(job_id, 1)
                
                if header_text:
                    page_headers.append((page_num - 1, header_text))  # Store 0-based
                    page_quality_flags[page_num - 1] = ocr_info.get('quality_flags', '')
                    logger.info(f"[JOB {job_id}] Page {page_num} header: '{header_text}'")
                    
                    # Record to CSV
                    self.csv_reporter.add_extraction(
                        pdf_filename=Path(pdf_path).name,
                        page_number=page_num,
                        header_extracted=header_text,
                        confidence_score=ocr_info.get('confidence_score', 0),
                        ocr_method=ocr_info.get('method', 'unknown'),
                        processing_time_ms=processing_time_ms,
                        render_scale=ocr_info.get('render_scale', 2.0),
                        status='success' if ocr_info.get('confidence_score', 0) >= 130 else 'low_confidence',
                        quality_flags=ocr_info.get('quality_flags', '')
                    )
                else:
                    # Record failed extraction
                    self.csv_reporter.add_extraction(
                        pdf_filename=Path(pdf_path).name,
                        page_number=page_num,
                        header_extracted='',
                        confidence_score=0,
                        ocr_method='failed',
                        processing_time_ms=processing_time_ms,
                        render_scale=2.0,
                        status='error',
                        error_message='No header extracted',
                        quality_flags=ocr_info.get('quality_flags', '')
                    )

            page_headers, rescue_updates = self._rescue_ambiguous_code_anchors(
                doc=doc,
                source_filename=Path(pdf_path).name,
                job_id=job_id,
                page_headers=page_headers,
                page_quality_flags=page_quality_flags,
            )
            if rescue_updates:
                for record in self.csv_reporter.pending_records:
                    page_idx = record.page_number - 1
                    new_header = rescue_updates.get(page_idx)
                    if not new_header:
                        continue
                    if record.header_extracted != new_header:
                        logger.warning(
                            f"[RESCUE] Page {record.page_number}: "
                            f"'{record.header_extracted}' -> '{new_header}'"
                        )
                        record.header_extracted = new_header
                        record.quality_flags = self._append_quality_flag(
                            record.quality_flags,
                            "code_anchor_rescued",
                        )

            if bool(getattr(self.config, "enable_code_anchor_harmonize", False)):
                # Optional post-pass harmonization, disabled by default to avoid
                # cross-page over-correction in mixed/random batches.
                page_headers, header_updates = self._harmonize_code_ambiguity_headers(
                    page_headers,
                    page_quality_flags,
                )
                if header_updates:
                    for record in self.csv_reporter.pending_records:
                        page_idx = record.page_number - 1
                        new_header = header_updates.get(page_idx)
                        if not new_header:
                            continue
                        if record.header_extracted != new_header:
                            logger.warning(
                                f"[HARMONIZE] Page {record.page_number}: "
                                f"'{record.header_extracted}' -> '{new_header}'"
                            )
                            record.header_extracted = new_header
                            record.quality_flags = self._append_quality_flag(
                                record.quality_flags,
                                "code_anchor_harmonized",
                            )
            
            doc.close()
            
            # Split PDF if enabled
            split_results = []
            if self.config.enable_pdf_splitting and page_headers:
                split_results = self.pdf_splitter.split_pdf(pdf_path, page_headers)
                
                # Update CSV with split group info
                for output_path, header_text, (start_page, end_page) in split_results:
                    # Find matching records and update split info
                    for record in self.csv_reporter.pending_records:
                        if (record.pdf_filename == Path(pdf_path).name and 
                            start_page <= record.page_number - 1 <= end_page):
                            record.split_group = header_text
                            record.output_filename = Path(output_path).name
            
            # End metrics tracking
            metrics = self.metrics_tracker.end_job(job_id)
            
            # Write CSV report
            summary_stats = {
                'total_pages': total_pages,
                'headers_extracted': len(page_headers),
                'split_pdfs_created': len(split_results),
                'processing_time_seconds': metrics.processing_time_seconds if metrics else 0,
                'avg_confidence': sum(r.confidence_score for r in self.csv_reporter.pending_records) / len(self.csv_reporter.pending_records) if self.csv_reporter.pending_records else 0,
                'code_ambiguity_pages': sum(
                    1 for r in self.csv_reporter.pending_records
                    if 'code_ambiguity:' in (r.quality_flags or '')
                )
            }
            
            # Filter error/low-confidence records BEFORE flushing
            error_records = [r for r in self.csv_reporter.pending_records 
                            if r.status in ['error', 'low_confidence']]
            
            # Flush main report
            csv_path = self.csv_reporter.flush_to_csv(job_id, summary_stats)
            
            # Generate error report if needed
            if csv_path and error_records:
                error_report = self.csv_reporter.create_error_report(csv_path, error_records)
                if error_report:
                    logger.warning(f"Error report generated: {error_report}")
            
            result = {
                'job_id': job_id,
                'pdf_path': pdf_path,
                'total_pages': total_pages,
                'headers_extracted': len(page_headers),
                'split_pdfs_created': len(split_results),
                'split_results': split_results,
                'metrics': metrics.to_dict() if metrics else None,
                'csv_report': str(csv_path) if csv_path else None,
                'success': True
            }
            
            logger.info(f"[JOB {job_id}] Processing complete!")
            logger.info(f"  Headers extracted: {len(page_headers)}")
            logger.info(f"  Split PDFs created: {len(split_results)}")
            if metrics:
                logger.info(f"  Processing time: {metrics.processing_time_seconds:.2f}s")
                logger.info(f"  Average confidence: {summary_stats['avg_confidence']:.2f}")
                logger.info(f"  Pages with code ambiguity: {summary_stats['code_ambiguity_pages']}")
                logger.info(f"  Avg page processing time: {metrics.processing_time_seconds / total_pages:.2f}s")
            if csv_path:
                logger.info(f"  CSV Report: {csv_path}")
            
            return result
        
        except Exception as e:
            logger.error(f"[JOB {job_id}] Error processing PDF: {e}", exc_info=True)
            self.metrics_tracker.record_error(job_id, str(e))
            self.metrics_tracker.end_job(job_id)
            
            return {
                'job_id': job_id,
                'pdf_path': pdf_path,
                'error': str(e),
                'success': False
            }
    
    def _extract_header_from_page(
        self,
        page,
        page_num: int,
        filename: str,
        job_id: str
    ) -> Tuple[str, dict]:
        """
        Extract header text from a single page
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (1-based)
            filename: PDF filename
            job_id: Job ID for metrics
        
        Returns:
            Tuple of (header_text, ocr_info_dict)
        """
        ocr_info = {
            'confidence_score': 0,
            'method': 'unknown',
            'render_scale': 2.0,
            'quality_flags': ''
        }
        
        try:
            # Calculate header region
            page_rect = page.rect
            page_height = page_rect.height
            page_width = page_rect.width
            
            # Convert percentage to coordinates
            top = (self.config.header_area_top / 100) * page_height
            left = (self.config.header_area_left / 100) * page_width
            width = (self.config.header_area_width / 100) * page_width
            height = (self.config.header_area_height / 100) * page_height
            
            rect = fitz.Rect(left, top, left + width, top + height)
            
            # Try direct text extraction first
            direct_text = page.get_text("text", clip=rect).strip()
            if direct_text:
                score, corrected = self.validator.validate_and_score(direct_text)
                strict_valid = self.validator.is_strict_header(
                    corrected if corrected else direct_text
                )
                if strict_valid and score > 0:
                    logger.info(f"[DIRECT] Got '{corrected}' (score: {score})")
                    ocr_info['confidence_score'] = score
                    ocr_info['method'] = 'direct'
                    ambiguity_flag = self._build_code_ambiguity_flag(corrected, page_num)
                    if ambiguity_flag:
                        ocr_info['quality_flags'] = ambiguity_flag
                    return corrected, ocr_info
                logger.debug(
                    f"[DIRECT] Rejected non-strict header '{corrected}' "
                    f"(score: {score}, strict_valid: {strict_valid}); fallback to OCR"
                )
            
            # OCR extraction with adaptive rendering
            context = OCRContext(
                filename=filename,
                page_num=page_num,
                job_id=job_id
            )
            
            text, method_results, freq_ratio = self.ocr_pipeline.extract_text_with_adaptive_rendering(
                page, rect, context
            )
            
            # Extract OCR info
            if text:
                score, _ = self.validator.validate_and_score(text)
                ocr_info['confidence_score'] = score
                ocr_info['method'] = list(method_results.keys())[0] if method_results else 'unknown'
                # Get render scale from context (default to 2.0)
                ocr_info['render_scale'] = 2.0  # Would need to track this from adaptive rendering

                meta = method_results.get("__meta__", {}) if isinstance(method_results, dict) else {}
                reason = str(meta.get("glyph_disambiguation_reason", "")).strip()
                ocr_info["glyph_disambiguation_reason"] = reason
                if meta.get("glyph_disambiguated"):
                    flag = "glyph_disambiguated" if not reason else f"glyph_disambiguated:{reason}"
                    ocr_info['quality_flags'] = self._append_quality_flag(
                        ocr_info.get('quality_flags', ''),
                        flag,
                    )
                elif reason:
                    ocr_info['quality_flags'] = self._append_quality_flag(
                        ocr_info.get('quality_flags', ''),
                        f"glyph_disambiguation_skipped:{reason}",
                    )

                ambiguity_flag = self._build_code_ambiguity_flag(text, page_num)
                if ambiguity_flag:
                    ocr_info['quality_flags'] = self._append_quality_flag(
                        ocr_info.get('quality_flags', ''),
                        ambiguity_flag,
                    )
            
            # Log to API
            if self.config.enable_api_logging:
                self.extraction_logger.log_extraction(
                    original_filename=filename,
                    page_number=page_num,
                    method_results=method_results,
                    direct_text=direct_text,
                    final_answer=text,
                    status="success"
                )
            
            return text, ocr_info
        
        except Exception as e:
            logger.error(f"Error extracting header from page {page_num}: {e}")
            
            # Log error to API
            if self.config.enable_api_logging:
                self.extraction_logger.log_extraction(
                    original_filename=filename,
                    page_number=page_num,
                    method_results={},
                    status="error",
                    error_message=str(e)
                )
            
            return "", ocr_info

    def _build_code_ambiguity_flag(self, header_text: str, page_num: int) -> str:
        """
        Build observe-only quality flag for code O/0 ambiguity.
        """
        ambiguity = self.validator.inspect_code_ambiguity(header_text)
        if not ambiguity.get('is_ambiguous'):
            return ""

        code_segment = str(ambiguity.get('code_segment', ''))
        alternatives = ambiguity.get('alternative_codes', []) or []
        alt_preview = "|".join(str(a) for a in alternatives[:3])

        logger.warning(
            f"[AMBIGUITY] Page {page_num}: customer code '{code_segment}' may be O/0 ambiguous "
            f"(alternatives: {alt_preview})"
        )
        return f"code_ambiguity:{code_segment}->{alt_preview}"

    def _append_quality_flag(self, existing: str, new_flag: str) -> str:
        """Append quality flag without duplicating tokens."""
        new_flag = str(new_flag or "").strip()
        if not new_flag:
            return existing or ""
        existing_tokens = [token.strip() for token in str(existing or "").split(";") if token.strip()]
        if new_flag in existing_tokens:
            return ";".join(existing_tokens)
        existing_tokens.append(new_flag)
        return ";".join(existing_tokens)

    def _harmonize_code_ambiguity_headers(
        self,
        page_headers: List[Tuple[int, str]],
        page_quality_flags: dict,
    ) -> Tuple[List[Tuple[int, str]], dict]:
        """
        Harmonize O/0 variants inside the same document using serial anchor evidence.

        Strategy:
        - Build anchor key with code signature (O->0), prefix/country and serial.
        - If multiple code variants exist for same anchor, choose canonical by:
          1) glyph_disambiguated support
          2) frequency
          3) presence of letter O
        """
        if not page_headers:
            return page_headers, {}

        variants_by_anchor = {}
        normalized_cache = {}

        for page_idx, header in page_headers:
            _, normalized = self.validator.validate_and_score(header)
            norm = normalized if normalized else header
            normalized_cache[page_idx] = norm

            parts = norm.split(self.config.expected_separator)
            code_idx = self._resolve_code_index(parts)
            if code_idx is None:
                continue

            code = parts[code_idx]
            if "0" not in code and "O" not in code:
                continue

            signature = code.replace("O", "0")
            anchor = self._build_code_anchor(parts, code_idx, signature)
            if anchor is None:
                continue

            entry = variants_by_anchor.setdefault(anchor, {})
            bucket = entry.setdefault(code, {"count": 0, "glyph": 0, "pages": []})
            bucket["count"] += 1
            flags = str(page_quality_flags.get(page_idx, "") or "")
            if "glyph_disambiguated" in flags:
                bucket["glyph"] += 1
            bucket["pages"].append(page_idx)

        canonical_by_anchor = {}
        min_glyph_support = max(
            1,
            int(getattr(self.config, "code_anchor_harmonize_min_glyph_support", 1)),
        )
        for anchor, code_map in variants_by_anchor.items():
            if len(code_map) <= 1:
                continue

            ranked = sorted(
                code_map.items(),
                key=lambda item: (
                    -item[1]["glyph"],
                    -item[1]["count"],
                    item[0],
                ),
            )

            top_code, top_meta = ranked[0]
            top_glyph = int(top_meta.get("glyph", 0))
            if top_glyph < min_glyph_support:
                # No strong per-page glyph evidence => do not harmonize this anchor.
                continue

            if len(ranked) > 1:
                second_code, second_meta = ranked[1]
                if (
                    int(second_meta.get("glyph", 0)) == top_glyph
                    and int(second_meta.get("count", 0)) == int(top_meta.get("count", 0))
                ):
                    logger.info(
                        f"[HARMONIZE] Skip anchor due to tie ({top_code} vs {second_code})"
                    )
                    continue

            canonical_by_anchor[anchor] = top_code

        if not canonical_by_anchor:
            return [(idx, normalized_cache[idx]) for idx, _ in page_headers], {}

        updates = {}
        updated_headers: List[Tuple[int, str]] = []
        for page_idx, _header in page_headers:
            norm = normalized_cache.get(page_idx, _header)
            parts = norm.split(self.config.expected_separator)
            code_idx = self._resolve_code_index(parts)
            if code_idx is None:
                updated_headers.append((page_idx, norm))
                continue

            signature = parts[code_idx].replace("O", "0")
            anchor = self._build_code_anchor(parts, code_idx, signature)
            canonical = canonical_by_anchor.get(anchor) if anchor is not None else None
            if canonical and parts[code_idx] != canonical:
                parts[code_idx] = canonical
                norm = self.config.expected_separator.join(parts)
                updates[page_idx] = norm

            updated_headers.append((page_idx, norm))

        return updated_headers, updates

    def _rescue_ambiguous_code_anchors(
        self,
        doc,
        source_filename: str,
        job_id: str,
        page_headers: List[Tuple[int, str]],
        page_quality_flags: dict,
    ) -> Tuple[List[Tuple[int, str]], dict]:
        """
        Rescue unresolved O/0 ambiguity for anchors that still have no char boxes.
        Runs one high-scale rescue per anchor, then propagates code segment inside anchor.
        """
        if not page_headers:
            return page_headers, {}
        if not bool(getattr(self.config, "enable_code_anchor_rescue_pass", True)):
            return page_headers, {}

        normalized_cache = {}
        anchors = {}

        for page_idx, header in page_headers:
            _, normalized = self.validator.validate_and_score(header)
            norm = normalized if normalized else header
            normalized_cache[page_idx] = norm

            ambiguity = self.validator.inspect_code_ambiguity(norm)
            if not ambiguity.get("is_ambiguous"):
                continue

            parts = norm.split(self.config.expected_separator)
            code_idx = self._resolve_code_index(parts)
            if code_idx is None:
                continue
            signature = parts[code_idx].replace("O", "0")
            anchor = self._build_code_anchor(parts, code_idx, signature)
            if anchor is None:
                continue

            flags = str(page_quality_flags.get(page_idx, "") or "")
            anchors.setdefault(anchor, []).append((page_idx, norm, flags))

        updates = {}
        rescue_only_no_boxes = bool(
            getattr(self.config, "code_anchor_rescue_only_on_no_char_boxes", True)
        )

        for anchor, items in anchors.items():
            if not items:
                continue
            if any("glyph_disambiguated" in flags for _idx, _h, flags in items):
                # Already resolved by per-page disambiguation.
                continue

            if rescue_only_no_boxes and not any(
                "glyph_disambiguation_skipped:no_char_boxes" in flags for _idx, _h, flags in items
            ):
                continue

            candidate_page_idx = None
            for page_idx, _header, flags in items:
                if "glyph_disambiguation_skipped:no_char_boxes" in flags:
                    candidate_page_idx = page_idx
                    break
            if candidate_page_idx is None:
                candidate_page_idx = items[0][0]

            page = doc[candidate_page_idx]
            rect = self._compute_header_rect(page)
            base_header = normalized_cache.get(candidate_page_idx, items[0][1])

            context = OCRContext(
                filename=source_filename,
                page_num=candidate_page_idx + 1,
                job_id=job_id,
            )
            rescued, reason = self.ocr_pipeline.rescue_ambiguous_header(
                page=page,
                rect=rect,
                context=context,
                base_header=base_header,
            )

            if rescued == base_header:
                logger.info(
                    f"[RESCUE] Anchor page {candidate_page_idx + 1}: no change ({reason})"
                )
                continue

            rescued_parts = rescued.split(self.config.expected_separator)
            rescued_code_idx = self._resolve_code_index(rescued_parts)
            if rescued_code_idx is None:
                continue
            rescued_code = rescued_parts[rescued_code_idx]

            for page_idx, old_header, _flags in items:
                old_parts = old_header.split(self.config.expected_separator)
                old_code_idx = self._resolve_code_index(old_parts)
                if old_code_idx is None:
                    continue
                if old_parts[old_code_idx] == rescued_code:
                    continue
                old_parts[old_code_idx] = rescued_code
                new_header = self.config.expected_separator.join(old_parts)
                normalized_cache[page_idx] = new_header
                updates[page_idx] = new_header
                logger.warning(
                    f"[RESCUE] Page {page_idx + 1}: '{old_header}' -> '{new_header}' ({reason})"
                )

        updated_headers = []
        for page_idx, header in page_headers:
            updated_headers.append((page_idx, normalized_cache.get(page_idx, header)))
        return updated_headers, updates

    def _compute_header_rect(self, page):
        """Compute configured header extraction rectangle for a page."""
        page_rect = page.rect
        page_height = page_rect.height
        page_width = page_rect.width

        top = (self.config.header_area_top / 100) * page_height
        left = (self.config.header_area_left / 100) * page_width
        width = (self.config.header_area_width / 100) * page_width
        height = (self.config.header_area_height / 100) * page_height
        return fitz.Rect(left, top, left + width, top + height)

    def _resolve_code_index(self, parts: List[str]) -> Optional[int]:
        if len(parts) == self.config.expected_parts:
            return 2
        if len(parts) == self.config.min_expected_parts:
            return 1
        return None

    def _build_code_anchor(self, parts: List[str], code_idx: int, code_signature: str):
        if code_idx >= len(parts):
            return None
        anchor_parts = list(parts)
        anchor_parts[code_idx] = code_signature
        return (
            len(anchor_parts),
            code_idx,
            *anchor_parts[:code_idx],
            *anchor_parts[code_idx + 1 :],
        )
    
    def shutdown(self):
        """Gracefully shutdown extractor"""
        logger.info("Shutting down PDFTextExtractorV3...")
        
        # Shutdown extraction logger
        if hasattr(self, 'extraction_logger'):
            self.extraction_logger.shutdown()
        
        # Export final metrics
        if self.metrics_tracker:
            self.metrics_tracker.export_to_json(self.config.metrics_export_path)
            self.metrics_tracker.print_summary()
        
        logger.info("Shutdown complete")


def main():
    """Example usage"""
    from v3.utils.config_manager import ConfigManager
    
    # Load configuration
    config_path = Path(__file__).parent / 'config.ini'
    config = ConfigManager.load_from_file(str(config_path))
    
    # Create extractor
    extractor = PDFTextExtractorV3(config)
    
    # Get PDF path from command line or use default
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'test_input/sample.pdf'
    
    # Process a PDF
    result = extractor.process_pdf(pdf_path)
    
    print(f"\nProcessing Result:")
    print(f"  Job ID: {result['job_id']}")
    print(f"  Headers extracted: {result.get('headers_extracted', 0)}")
    print(f"  Split PDFs: {result.get('split_pdfs_created', 0)}")
    
    # Cleanup
    extractor.shutdown()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
