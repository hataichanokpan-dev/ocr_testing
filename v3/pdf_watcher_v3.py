"""
PDF Watcher Service for V3
Monitors input folder and processes PDFs automatically with new organized output structure
"""

import os
import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

# Ensure workspace root is on sys.path so `import v3` works when running
# this file directly (e.g. `python v3\pdf_watcher_v3.py`)
try:
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    pass

from v3.pdf_extractor_v3 import PDFTextExtractorV3
from v3.utils.config_manager import ConfigManager
from v3.utils.metrics_tracker import MetricsTracker

# Setup logging
def setup_logging():
    """Setup logging for service"""
    log_folder = Path('logs')
    log_folder.mkdir(exist_ok=True)
    
    log_file = log_folder / f'pdf_watcher_v3_{datetime.now().strftime("%Y%m%d")}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)


class PDFHandler(FileSystemEventHandler):
    """Handler for PDF file events"""
    
    def __init__(self, extractor: PDFTextExtractorV3, metrics: MetricsTracker):
        self.extractor = extractor
        self.metrics = metrics
        self.processing = set()
    
    def on_created(self, event):
        """Handle file creation event"""
        if event.is_directory:
            return
        
        if not event.src_path.lower().endswith('.pdf'):
            return
        
        # Avoid duplicate processing
        if event.src_path in self.processing:
            return
        
        try:
            self.processing.add(event.src_path)
            logger.info(f"Detected new PDF: {event.src_path}")
            
            # Wait and validate file is complete and not corrupted
            if not self._wait_for_file_ready(event.src_path):
                logger.warning(f"File not ready or corrupted, skipping: {event.src_path}")
                return
            
            # Process PDF
            result = self.extractor.process_pdf(event.src_path)
            
            # Log actual result
            if result.get('success', True) and not result.get('error'):
                logger.info(f"Successfully processed: {event.src_path} - "
                           f"Headers: {result.get('headers_extracted', 0)}, "
                           f"Splits: {result.get('split_pdfs_created', 0)}")
            else:
                logger.error(f"Failed to process: {event.src_path} - {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            logger.error(f"Error processing {event.src_path}: {e}", exc_info=True)
        
        finally:
            self.processing.discard(event.src_path)
    
    def _wait_for_file_ready(self, filepath: str, max_attempts: int = 5) -> bool:
        """Wait for file to be fully written and validate it's not corrupted"""
        import os
        
        for attempt in range(max_attempts):
            try:
                # Wait before checking
                time.sleep(2 if attempt == 0 else 1)
                
                # Check file exists and has size
                if not os.path.exists(filepath):
                    logger.warning(f"File disappeared: {filepath}")
                    return False
                
                file_size = os.path.getsize(filepath)
                if file_size == 0:
                    logger.warning(f"File is empty (attempt {attempt + 1}/{max_attempts})")
                    continue
                
                # Try to open with fitz to validate
                try:
                    import fitz
                    doc = fitz.open(filepath)
                    page_count = len(doc)
                    doc.close()
                    
                    if page_count > 0:
                        logger.debug(f"File ready: {filepath} ({file_size} bytes, {page_count} pages)")
                        return True
                    else:
                        logger.warning(f"PDF has no pages (attempt {attempt + 1}/{max_attempts})")
                        continue
                
                except Exception as e:
                    logger.warning(f"File not ready or corrupted (attempt {attempt + 1}/{max_attempts}): {e}")
                    continue
            
            except Exception as e:
                logger.error(f"Error checking file readiness: {e}")
                continue
        
        logger.error(f"File failed validation after {max_attempts} attempts: {filepath}")
        return False


def main():
    """Main service loop"""
    logger.info("="*60)
    logger.info("PDF Watcher Service V3 Starting...")
    logger.info("="*60)
    
    # Load configuration
    config_path = Path(__file__).parent / 'config.ini'
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return
    
    config = ConfigManager.load_from_file(str(config_path))
    logger.info(f"Configuration loaded from: {config_path}")
    
    # Initialize components
    metrics = MetricsTracker(enable_tracking=config.enable_metrics_tracking)
    extractor = PDFTextExtractorV3(config, metrics_tracker=metrics)
    
    # Setup input folder monitoring (from config)
    input_folder = Path(config.input_folder)
    input_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Monitoring input folder: {input_folder.absolute()}")
    
    # Setup observer
    event_handler = PDFHandler(extractor, metrics)
    observer = Observer()
    observer.schedule(event_handler, str(input_folder), recursive=False)
    observer.start()
    
    logger.info("Service is running. Press Ctrl+C to stop.")
    logger.info("="*60)
    
    try:
        while True:
            time.sleep(60)
            
            # Export metrics every 6 hours (reduce log spam)
            if int(time.time()) % 21600 < 60:
                metrics.export_to_json(config.metrics_export_path)
                logger.debug("Metrics exported (6-hour interval)")
    
    except KeyboardInterrupt:
        logger.info("Shutdown signal received...")
        observer.stop()
    
    observer.join()
    
    # Final metrics
    logger.info("="*60)
    logger.info("Service Shutdown - Final Metrics:")
    metrics.print_summary()
    logger.info("="*60)
    
    # Cleanup
    extractor.shutdown()


if __name__ == '__main__':
    main()
