"""
PDF Folder Watcher
Monitors a folder for new PDF files, extracts header text, and renames them
"""

import os
import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime
from configparser import ConfigParser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import both extractor versions
try:
    from pdf_extractorV2 import PDFTextExtractor as PDFTextExtractorV2
    EXTRACTOR_V2_AVAILABLE = True
except ImportError:
    EXTRACTOR_V2_AVAILABLE = False
    
from pdf_extractor import PDFTextExtractor


class PDFFileHandler(FileSystemEventHandler):
    """Handles file system events for PDF files"""
    
    def __init__(self, config, extractor):
        """
        Initialize the file handler
        
        Args:
            config: ConfigParser object with settings
            extractor: PDFTextExtractor instance
        """
        self.config = config
        self.extractor = extractor
        self.watch_folder = config.get('Settings', 'watch_folder')
        self.output_folder = config.get('Settings', 'output_folder', fallback='')
        self.delete_original = config.getboolean('Settings', 'delete_original', fallback=False)
        self.add_timestamp = config.getboolean('Settings', 'add_timestamp', fallback=False)
        self.file_extension = config.get('Settings', 'file_extension', fallback='.pdf')
        self.processing = set()  # Track files being processed
        self.processed_files = set()  # Track files already processed
        
    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Check if it's a PDF file
        if not file_path.lower().endswith('.pdf'):
            return
        
        # Avoid processing the same file multiple times
        if file_path in self.processing:
            return
        
        # Skip files we just created
        if file_path in self.processed_files:
            return
        
        logger.info(f"New PDF detected: {file_path}")
        
        # Wait a moment to ensure file is fully written
        time.sleep(2)
        
        # Process the file
        self.process_pdf(file_path)
    
    def process_pdf(self, file_path):
        """
        Process a PDF file: extract text and rename
        
        Args:
            file_path: Path to the PDF file
        """
        try:
            self.processing.add(file_path)
            
            # Check if file still exists and is accessible
            if not os.path.exists(file_path):
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Wait for file to be fully written (check file size stability)
            if not self._wait_for_file_ready(file_path):
                logger.warning(f"File not ready or inaccessible: {file_path}")
                return
            
            # Extract header text
            header_text = self.extractor.extract_header_text(file_path)
            
            # Get original filename without extension as fallback
            original_name = Path(file_path).stem
            
            if not header_text:
                logger.warning(f"No text extracted from: {file_path}, keeping original name")
            
            # Sanitize filename (will use original name if header_text is empty)
            new_name = self.extractor.sanitize_filename(header_text, original_filename=original_name)
            
            # Add timestamp if configured
            if self.add_timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{new_name}_{timestamp}"
            
            # Add extension
            new_name = f"{new_name}{self.file_extension}"
            
            # Determine output path
            if self.output_folder and os.path.exists(self.output_folder):
                output_path = os.path.join(self.output_folder, new_name)
            else:
                output_dir = os.path.dirname(file_path)
                output_path = os.path.join(output_dir, new_name)
            
            # Handle duplicate filenames
            output_path = self._get_unique_filename(output_path)
            
            # Mark output file as processed to avoid re-processing
            self.processed_files.add(output_path)
            
            # Copy or move the file
            if self.delete_original:
                shutil.move(file_path, output_path)
                logger.info(f"Moved and renamed: {file_path} -> {output_path}")
            else:
                shutil.copy2(file_path, output_path)
                logger.info(f"Copied and renamed: {file_path} -> {output_path}")
            
            logger.info(f"Successfully processed: {new_name}")
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
        finally:
            if file_path in self.processing:
                self.processing.remove(file_path)
    
    def _wait_for_file_ready(self, file_path, timeout=30):
        """
        Wait for file to be fully written and accessible
        
        Args:
            file_path: Path to the file
            timeout: Maximum wait time in seconds
            
        Returns:
            bool: True if file is ready, False otherwise
        """
        start_time = time.time()
        last_size = -1
        
        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(file_path)
                
                if current_size == last_size and current_size > 0:
                    # File size stable, try to open it
                    with open(file_path, 'rb') as f:
                        f.read(1)
                    return True
                
                last_size = current_size
                time.sleep(1)
                
            except (OSError, IOError):
                time.sleep(1)
                continue
        
        return False
    
    def _get_unique_filename(self, file_path):
        """
        Generate unique filename if file already exists
        
        Args:
            file_path: Desired file path
            
        Returns:
            str: Unique file path
        """
        if not os.path.exists(file_path):
            return file_path
        
        base_path = Path(file_path)
        base_name = base_path.stem
        extension = base_path.suffix
        directory = base_path.parent
        
        counter = 1
        while True:
            new_path = directory / f"{base_name}_{counter}{extension}"
            if not os.path.exists(new_path):
                return str(new_path)
            counter += 1


def setup_logging(config):
    """Setup logging configuration"""
    log_level = config.get('Logging', 'log_level', fallback='INFO')
    log_file = config.get('Logging', 'log_file', fallback='pdf_watcher.log')
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)


def load_config():
    """Load configuration from config.ini"""
    config = ConfigParser()
    config_file = 'config.ini'
    
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found!")
        print("Please create config.ini with the required settings.")
        sys.exit(1)
    
    config.read(config_file)
    return config


def validate_config(config):
    """Validate configuration settings"""
    watch_folder = config.get('Settings', 'watch_folder')
    
    if not watch_folder:
        logger.error("watch_folder not specified in config.ini")
        return False
    
    if not os.path.exists(watch_folder):
        logger.error(f"Watch folder does not exist: {watch_folder}")
        return False
    
    output_folder = config.get('Settings', 'output_folder', fallback='')
    if output_folder and not os.path.exists(output_folder):
        logger.warning(f"Output folder does not exist: {output_folder}")
        logger.info("Files will be renamed in the same folder as originals")
    
    return True


def main():
    """Main function to start the PDF watcher"""
    # Load configuration
    config = load_config()
    
    # Setup logging
    global logger
    logger = setup_logging(config)
    
    logger.info("=" * 60)
    logger.info("PDF Folder Watcher Started")
    logger.info("=" * 60)
    
    # Validate configuration
    if not validate_config(config):
        logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)
    
    watch_folder = config.get('Settings', 'watch_folder')
    logger.info(f"Watching folder: {watch_folder}")
    
    # Select extractor version based on configuration
    use_extractor_v2 = config.getboolean('Settings', 'use_extractor_v2', fallback=False)
    
    if use_extractor_v2:
        if EXTRACTOR_V2_AVAILABLE:
            logger.info("[V2] Using PDFTextExtractorV2 (optimized with parallel processing)")
            extractor = PDFTextExtractorV2(config)
        else:
            logger.warning("PDFTextExtractorV2 not available, falling back to standard extractor")
            logger.info("[V1] Using PDFTextExtractor (standard version)")
            extractor = PDFTextExtractor(config)
    else:
        logger.info("[V1] Using PDFTextExtractor (standard version)")
        extractor = PDFTextExtractor(config)
    
    # Initialize file handler
    event_handler = PDFFileHandler(config, extractor)
    
    # Create observer
    observer = Observer()
    observer.schedule(event_handler, watch_folder, recursive=False)
    observer.start()
    
    logger.info("Monitoring started. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping PDF watcher...")
        observer.stop()
    
    observer.join()
    logger.info("PDF watcher stopped.")


if __name__ == "__main__":
    main()
