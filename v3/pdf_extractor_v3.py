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
                        status='success' if ocr_info.get('confidence_score', 0) >= 130 else 'low_confidence'
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
                        error_message='No header extracted'
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
                'avg_confidence': sum(r.confidence_score for r in self.csv_reporter.pending_records) / len(self.csv_reporter.pending_records) if self.csv_reporter.pending_records else 0
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
            'render_scale': 2.0
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
