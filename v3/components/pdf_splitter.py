"""
PDF Splitter - Split PDFs based on header changes
Extracted from V2 with improvements
"""

import fitz  # PyMuPDF
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from v3.utils.config_manager import ExtractionConfig
from v3.components.header_validator import HeaderValidator
from v3.components.output_organizer import OutputOrganizer

logger = logging.getLogger(__name__)


class PdfSplitter:
    """
    Splits PDF files based on header text changes
    
    Features:
    - Detect header changes across pages
    - Create separate PDFs for each header group
    - Organized output with OutputOrganizer
    - Serial-based or similarity-based matching
    """
    
    def __init__(
        self,
        config: ExtractionConfig,
        validator: HeaderValidator,
        output_organizer: OutputOrganizer
    ):
        """
        Initialize PDF splitter
        
        Args:
            config: Extraction configuration
            validator: Header validator for comparison
            output_organizer: Output organizer for file paths
        """
        self.config = config
        self.validator = validator
        self.output_organizer = output_organizer
    
    def split_pdf(
        self,
        pdf_path: str,
        page_headers: List[Tuple[int, str]]
    ) -> List[Tuple[Path, str, Tuple[int, int]]]:
        """
        Split PDF based on header changes
        
        Args:
            pdf_path: Path to source PDF
            page_headers: List of (page_num, header_text) tuples
        
        Returns:
            List of (output_path, header_text, (start_page, end_page)) tuples
        """
        if not self.config.enable_pdf_splitting:
            logger.info("PDF splitting disabled in config")
            return []
        
        if len(page_headers) == 0:
            logger.warning("No headers provided for splitting")
            return []
        
        logger.info(f"Starting PDF split: {pdf_path}")
        
        # Detect header groups
        groups = self._detect_header_groups(page_headers)
        
        # Open source PDF
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            return []
        
        # If only one group, copy entire PDF to organized output
        if len(groups) <= 1:
            logger.info("Only one header group detected, copying entire PDF to organized output")
            try:
                # Get header text
                header_text = groups[0][2] if groups else "UNKNOWN"
                safe_header = self._sanitize_filename(header_text)
                
                # Generate filename
                original_name = Path(pdf_path).stem
                total_pages = len(doc)
                filename = self.config.split_naming_pattern.format(
                    header=safe_header,
                    start=1,
                    end=total_pages,
                    original=original_name,
                    index=1
                )
                
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                
                # Get organized output path (overwrite if exists)
                output_path = self.output_organizer.get_output_path(filename)
                
                # Copy entire PDF
                success = self._create_pdf_subset(doc, 0, total_pages - 1, output_path)
                
                doc.close()
                
                if success:
                    logger.info(f"Copied PDF to: {output_path} (header: {header_text})")
                    return [(output_path, header_text, (0, total_pages - 1))]
                else:
                    return []
            except Exception as e:
                logger.error(f"Failed to copy PDF: {e}")
                doc.close()
                return []
        
        logger.info(f"Detected {len(groups)} header groups")
        
        results = []
        original_name = Path(pdf_path).stem
        
        # Create split PDFs
        for idx, (start_page, end_page, header_text) in enumerate(groups, 1):
            try:
                # Sanitize header for filename
                safe_header = self._sanitize_filename(header_text)
                
                # Generate filename from pattern
                filename = self.config.split_naming_pattern.format(
                    header=safe_header,
                    start=start_page + 1,  # 1-based for display
                    end=end_page + 1,
                    original=original_name,
                    index=idx
                )
                
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                
                # Get organized output path (overwrite if exists)
                output_path = self.output_organizer.get_output_path(filename)
                
                # Create new PDF with pages
                success = self._create_pdf_subset(doc, start_page, end_page, output_path)
                
                if success:
                    results.append((output_path, header_text, (start_page, end_page)))
                    logger.info(
                        f"Created split PDF: {output_path.name} "
                        f"(pages {start_page + 1}-{end_page + 1}, header: {header_text})"
                    )
            
            except Exception as e:
                logger.error(f"Failed to create split PDF for group {idx}: {e}")
        
        doc.close()
        
        logger.info(f"Split complete: created {len(results)} PDF(s)")
        return results
    
    def _detect_header_groups(
        self,
        page_headers: List[Tuple[int, str]]
    ) -> List[Tuple[int, int, str]]:
        """
        Detect groups of consecutive pages with same/similar headers
        
        Args:
            page_headers: List of (page_num, header_text) tuples
        
        Returns:
            List of (start_page, end_page, header_text) tuples (0-based page numbers)
        """
        if not page_headers:
            return []
        
        groups = []
        current_start = page_headers[0][0]
        current_header = page_headers[0][1]
        current_headers = [current_header]
        
        for i in range(1, len(page_headers)):
            page_num, header = page_headers[i]
            
            # Check if header matches current group
            if self.validator.headers_match(
                header,
                current_header,
                self.config.header_similarity_threshold
            ):
                # Same group
                current_headers.append(header)
            else:
                # New group - save previous
                best_header = self._select_best_header(current_headers)
                groups.append((current_start, page_headers[i - 1][0], best_header))
                
                # Start new group
                current_start = page_num
                current_header = header
                current_headers = [header]
        
        # Add last group
        best_header = self._select_best_header(current_headers)
        groups.append((current_start, page_headers[-1][0], best_header))
        
        # Filter by min_pages_per_split
        if self.config.min_pages_per_split > 1:
            filtered = []
            for start, end, header in groups:
                page_count = end - start + 1
                if page_count >= self.config.min_pages_per_split:
                    filtered.append((start, end, header))
                else:
                    logger.debug(f"Skipping group with {page_count} pages (min: {self.config.min_pages_per_split})")
            groups = filtered
        
        return groups
    
    def _select_best_header(self, headers: List[str]) -> str:
        """Select the best header from a list of similar headers"""
        if not headers:
            return ""
        
        if len(headers) == 1:
            return headers[0]
        
        # Score each header and pick best
        scored = []
        for header in headers:
            score, _ = self.validator.validate_and_score(header)
            scored.append((score, header))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def _create_pdf_subset(
        self,
        source_doc: fitz.Document,
        start_page: int,
        end_page: int,
        output_path: Path
    ) -> bool:
        """
        Create new PDF from page range
        
        Args:
            source_doc: Source document
            start_page: Start page (0-based, inclusive)
            end_page: End page (0-based, inclusive)
            output_path: Output file path
        
        Returns:
            bool: True if successful
        """
        try:
            # Create new document
            new_doc = fitz.open()
            
            # Insert pages
            new_doc.insert_pdf(
                source_doc,
                from_page=start_page,
                to_page=end_page
            )
            
            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            new_doc.save(str(output_path))
            new_doc.close()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to create PDF subset: {e}")
            return False
    
    def _sanitize_filename(self, text: str) -> str:
        """Convert text to safe filename"""
        if not text:
            return "unnamed"
        
        # Remove or replace invalid characters
        if self.config.remove_special_chars:
            text = re.sub(r'[^\w\s-]', '', text)
        
        # Replace spaces
        text = text.replace(' ', self.config.replace_spaces_with)
        
        # Remove multiple consecutive separators
        text = re.sub(r'[_-]+', '_', text)
        
        # Trim to max length
        text = text[:self.config.max_filename_length]
        
        # Remove leading/trailing separators
        text = text.strip('_-')
        
        return text if text else "unnamed"
