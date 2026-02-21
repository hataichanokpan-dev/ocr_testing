"""
PDF Text Extractor Module
Extracts text from specific regions of PDF files
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import cv2
import numpy as np
import requests
import json

# Configure Tesseract path for Windows
if os.name == 'nt':  # Windows
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

logger = logging.getLogger(__name__)


class PDFTextExtractor:
    def __init__(self, config):
        """
        Initialize PDF text extractor with configuration
        
        Args:
            config: ConfigParser object with settings
        """
        self.config = config
        self.header_top = float(config.get('Settings', 'header_area_top', fallback='0'))
        self.header_left = float(config.get('Settings', 'header_area_left', fallback='0'))
        self.header_width = float(config.get('Settings', 'header_area_width', fallback='100'))
        self.header_height = float(config.get('Settings', 'header_area_height', fallback='15'))
        
        # Parse pages to read
        pages_str = config.get('Settings', 'pages_to_read', fallback='1')
        self.pages_to_read = [int(p.strip()) for p in pages_str.split(',') if p.strip().isdigit()]
        
        # Format validation settings
        self.expected_parts = config.getint('Settings', 'expected_parts', fallback=4)
        self.expected_separator = config.get('Settings', 'expected_separator', fallback='-')
        self.expected_digit_count = config.getint('Settings', 'expected_digit_count', fallback=8)
        self.min_digit_count = config.getint('Settings', 'min_digit_count', fallback=6)
        
        # Pattern-based validation (more precise)
        # Format: [Prefix:1]-[Country/Region:1-2]-[Code/Type:2-4]-[Serial/ID:7-10]
        self.enable_pattern_validation = config.getboolean('Settings', 'enable_pattern_validation', fallback=True)
        self.pattern_prefix_length = config.getint('Settings', 'pattern_prefix_length', fallback=1)
        self.pattern_country_min = config.getint('Settings', 'pattern_country_min', fallback=1)
        self.pattern_country_max = config.getint('Settings', 'pattern_country_max', fallback=2)
        self.pattern_code_min = config.getint('Settings', 'pattern_code_min', fallback=2)
        self.pattern_code_max = config.getint('Settings', 'pattern_code_max', fallback=4)
        self.pattern_serial_min = config.getint('Settings', 'pattern_serial_min', fallback=7)
        self.pattern_serial_max = config.getint('Settings', 'pattern_serial_max', fallback=10)
        
        # Serial/ID strict validation (first char must be from allowed list, rest must be digits)
        allowed_prefixes_str = config.get('Settings', 'pattern_serial_allowed_prefixes', fallback='')
        self.pattern_serial_allowed_prefixes = [p.strip().upper() for p in allowed_prefixes_str.split(',') if p.strip()]
        
        # API logging configuration
        self.api_url = config.get('Settings', 'api_log_url', 
                                  fallback='http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog')
        self.enable_api_logging = config.getboolean('Settings', 'enable_api_logging', fallback=True)
        
        # Performance optimization settings
        self.enable_parallel_processing = config.getboolean('Settings', 'enable_parallel_processing', fallback=True)
        self.max_workers = config.getint('Settings', 'max_workers', fallback=4)
        
        # OCR optimization settings
        self.ocr_filter_black_text = config.getboolean('Settings', 'ocr_filter_black_text', fallback=True)
        self.ocr_black_threshold = config.getint('Settings', 'ocr_black_threshold', fallback=100)
        
        # Debug image settings
        self.save_debug_images = config.getboolean('Settings', 'save_debug_images', fallback=True)
        self.debug_images_folder = config.get('Settings', 'debug_images_folder', fallback='debug_images')
        self.organize_by_date = config.getboolean('Settings', 'organize_by_date', fallback=True)
        self.save_method_images = config.getboolean('Settings', 'save_method_images', fallback=True)
        self.image_retention_days = config.getint('Settings', 'image_retention_days', fallback=30)
        
        # Create debug folder if needed
        if self.save_debug_images:
            self._setup_debug_folder()
        
        # Method execution order (best performing methods first for better user feedback)
        self.method_priority = ['method2', 'method3', 'method4', 'method5', 'method1', 'method6', 'method0B', 'method0C', 'method7', 'method0']
    
    def _setup_debug_folder(self):
        """Create debug folder structure and clean old images"""
        try:
            base_folder = Path(self.debug_images_folder)
            base_folder.mkdir(exist_ok=True)
            logger.info(f"Debug images folder: {base_folder.absolute()}")
            
            # Clean old images if retention policy is set
            if self.image_retention_days > 0:
                self._cleanup_old_images(base_folder)
        except Exception as e:
            logger.error(f"Failed to setup debug folder: {e}")
    
    def _cleanup_old_images(self, base_folder):
        """Delete images older than retention days"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=self.image_retention_days)
            deleted_count = 0
            
            # Iterate through all files and subfolders
            for file_path in base_folder.rglob('*.png'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old debug images (older than {self.image_retention_days} days)")
        except Exception as e:
            logger.error(f"Failed to cleanup old images: {e}")
    
    def _get_debug_path(self, original_filename, page_num, method_name=""):
        """Generate debug image path with proper organization"""
        if not self.save_debug_images:
            return None
        
        try:
            base_folder = Path(self.debug_images_folder)
            
            # Organize by date if enabled
            if self.organize_by_date:
                date_folder = base_folder / datetime.now().strftime("%Y-%m-%d")
                date_folder.mkdir(parents=True, exist_ok=True)
                save_folder = date_folder
            else:
                save_folder = base_folder
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%H%M%S")
            filename_base = Path(original_filename).stem if original_filename else "unknown"
            
            if method_name:
                # Method-specific image (e.g., method2_threshold)
                filename = f"{filename_base}_page{page_num}_{timestamp}_{method_name}.png"
            else:
                # Original extracted area
                filename = f"{filename_base}_page{page_num}_{timestamp}_original.png"
            
            return str(save_folder / filename)
        except Exception as e:
            logger.error(f"Failed to generate debug path: {e}")
            return f"debug_page{page_num}.png"  # Fallback
        
    def extract_header_text(self, pdf_path):
        """
        Extract text from the header area of a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            str: Extracted text from header area
        """
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            
            # Open PDF
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                logger.warning("PDF has no pages")
                return ""
            
            logger.info(f"PDF has {len(doc)} pages. Will read pages: {self.pages_to_read}")
            
            all_results = []  # Store tuples of (text, score, page_num, frequency)
            
            # Process each specified page
            for page_num in self.pages_to_read:
                # Check if page exists (convert to 0-based index)
                if page_num < 1 or page_num > len(doc):
                    logger.warning(f"Page {page_num} does not exist in PDF")
                    continue
                
                page = doc[page_num - 1]  # Convert to 0-based index
                logger.info(f"Processing page {page_num}...")
                
                page_rect = page.rect
                
                # Calculate header area (convert percentage to pixels if needed)
                if self.header_width <= 100 and self.header_height <= 100:
                    # Treat as percentage
                    x0 = page_rect.width * (self.header_left / 100)
                    y0 = page_rect.height * (self.header_top / 100)
                    x1 = page_rect.width * ((self.header_left + self.header_width) / 100)
                    y1 = page_rect.height * ((self.header_top + self.header_height) / 100)
                else:
                    # Treat as pixels
                    x0, y0 = self.header_left, self.header_top
                    x1 = x0 + self.header_width
                    y1 = y0 + self.header_height
                
                # Create rectangle for header area
                header_rect = fitz.Rect(x0, y0, x1, y1)
                
                # Try to extract text directly first
                direct_text = page.get_text("text", clip=header_rect).strip()
                original_filename = Path(pdf_path).stem
                
                if direct_text:
                    logger.info(f"Page {page_num}: Extracted text directly: {direct_text}")
                    direct_score = self._validate_and_score_result(direct_text)
                    all_results.append((direct_text, direct_score, page_num, 1.0))
                    
                    # Log successful direct extraction to API
                    if self.enable_api_logging:
                        self._send_extraction_log(
                            original_filename=original_filename,
                            page_number=page_num,
                            method_results={},
                            direct_text=direct_text,
                            direct_score=direct_score,
                            final_answer=direct_text,
                            debug_image_path="",
                            status="direct_extraction_success"
                        )
                else:
                    # If no text found, use OCR
                    logger.info(f"Page {page_num}: No text found, attempting OCR...")
                    text, method_results, freq_ratio = self._ocr_extract_with_confidence(
                        page, header_rect, page_num, original_filename, direct_text
                    )
                    if text:
                        score = self._validate_and_score_result(text)
                        all_results.append((text, score, page_num, freq_ratio))
            
            doc.close()
            
            # Combine and analyze results from all pages
            if all_results:
                final_text = self._select_best_result_from_pages(all_results)
                logger.info(f"Final extracted text: {final_text}")
                return final_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""
    
    def _ocr_extract_with_confidence(self, page, rect, page_num=1, original_filename="", direct_text=""):
        """
        Use OCR to extract text from a specific area with confidence metrics
        
        Args:
            page: PyMuPDF page object
            rect: Rectangle area to extract
            page_num: Page number for debug logging
            original_filename: Original PDF filename for logging
            direct_text: Text extracted directly from PDF (if any)
            
        Returns:
            tuple: (text, method_results, frequency_ratio)
        """
        try:
            # Render the area as image at very high resolution (6x for better OCR)
            mat = fitz.Matrix(6, 6)  # 6x zoom for better OCR with bold text
            pix = page.get_pixmap(matrix=mat, clip=rect)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Save debug image to see what's being extracted
            debug_path = self._get_debug_path(original_filename, page_num)
            if debug_path:
                img.save(debug_path)
                logger.info(f"Debug: Saved extracted area to {debug_path}")
            else:
                debug_path = ""
            
            # Try multiple preprocessing methods and get detailed results
            text, method_results, freq_ratio = self._try_multiple_ocr_methods(img, original_filename, page_num)
            
            # Log to API
            if self.enable_api_logging:
                self._send_extraction_log(
                    original_filename=original_filename,
                    page_number=page_num,
                    method_results=method_results,
                    direct_text=direct_text,
                    final_answer=text,
                    debug_image_path=debug_path,
                    status="success" if text else "no_text_found"
                )
            
            if text:
                logger.info(f"OCR extracted: {text}")
            else:
                logger.warning("OCR could not extract any text")
            
            return text, method_results, freq_ratio
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            
            # Log error to API
            if self.enable_api_logging:
                self._send_extraction_log(
                    original_filename=original_filename,
                    page_number=page_num,
                    method_results={},
                    direct_text=direct_text,
                    final_answer="",
                    debug_image_path="",
                    status="error",
                    error_message=str(e)
                )
            
            return "", {}, 0.0
    
    def _validate_and_score_result(self, text):
        """
        Validate and score OCR result based on expected format from config
        
        Args:
            text: OCR extracted text
            
        Returns:
            int: Score (higher is better), -1 if invalid
        """
        if not text or len(text) < 10:
            return -1
        
        score = 0
        
        # Use pattern-based validation if enabled
        if self.enable_pattern_validation:
            return self._validate_with_pattern(text)
        
        # Fallback to legacy validation
        # Split by configured separator
        parts = text.split(self.expected_separator)
        
        # Check if matches expected number of parts
        if len(parts) == self.expected_parts:
            score += 50
            
            # Last part should contain digits
            last_part = parts[-1]
            
            # Check if last part has sufficient length
            if len(last_part) >= 8:
                score += 10
                
                # Count digits in last part
                digit_count = sum(c.isdigit() for c in last_part)
                
                # Score based on digit count
                if digit_count == self.expected_digit_count:
                    score += 100  # High score for exact match
                    logger.info(f"  [OK] Valid format with {self.expected_digit_count} digits: {text}")
                elif digit_count == self.expected_digit_count - 1:
                    score += 50  # Acceptable if 1 digit off
                elif digit_count >= self.min_digit_count:
                    score += 20
                
                # Check if starts with single letter followed by digits (perfect format)
                if len(last_part) == self.expected_digit_count + 1 and last_part[0].isalpha() and last_part[1:].isdigit():
                    score += 50  # Perfect format like S17893848
                    logger.info(f"  [PERFECT] Ideal format: {text}")
                
                # Penalize if too many letters in last part
                letter_count = sum(c.isalpha() for c in last_part)
                if letter_count > 1:
                    score -= 30 * (letter_count - 1)  # Penalize extra letters
                    logger.info(f"  [WARN] Too many letters in last part ({letter_count}): {text}")
        
        # Additional checks for overall quality
        total_digits = sum(c.isdigit() for c in text)
        if total_digits >= self.expected_digit_count:
            score += 20
        
        logger.info(f"  Score: {score} for '{text}'")
        return score
    
    def _validate_with_pattern(self, text):
        """
        Validate text using detailed pattern rules
        Format: [Prefix:1]-[Country/Region:1-2]-[Code/Type:2-4]-[Serial/ID:7-10]
        Example: B-C-5U5-R4091534
        
        Args:
            text: Text to validate
            
        Returns:
            int: Score (higher is better), -1 if invalid
        """
        score = 0
        
        # Split by separator
        parts = text.split(self.expected_separator)
        
        # Must have exactly 4 parts
        if len(parts) != self.expected_parts:
            logger.info(f"  [PATTERN] Invalid part count: {len(parts)} (expected {self.expected_parts})")
            return -1
        
        score += 60  # Base score for correct structure
        
        # Validate Part 1: Prefix (1 letter)
        prefix = parts[0]
        if len(prefix) == self.pattern_prefix_length and prefix.isalpha():
            score += 30
            logger.info(f"  [PATTERN] [OK] Prefix '{prefix}' valid (1 letter)")
        else:
            score -= 20
            logger.info(f"  [PATTERN] [X] Prefix '{prefix}' invalid (expected 1 letter)")
        
        # Validate Part 2: Country/Region (1-2 letters)
        country = parts[1]
        if (self.pattern_country_min <= len(country) <= self.pattern_country_max and 
            country.isalpha()):
            score += 30
            logger.info(f"  [PATTERN] [OK] Country '{country}' valid ({len(country)} letter(s))")
        else:
            score -= 20
            logger.info(f"  [PATTERN] [X] Country '{country}' invalid (expected 1-2 letters)")
        
        # Validate Part 3: Code/Type (2-4 alphanumeric)
        code = parts[2]
        if (self.pattern_code_min <= len(code) <= self.pattern_code_max and 
            code.isalnum()):
            score += 30
            logger.info(f"  [PATTERN] [OK] Code '{code}' valid ({len(code)} char(s))")
        else:
            score -= 20
            logger.info(f"  [PATTERN] [X] Code '{code}' invalid (expected 2-4 alphanumeric)")
        
        # Validate Part 4: Serial/ID (7-10 alphanumeric)
        serial = parts[3].strip()  # Remove trailing spaces
        serial_clean = ''.join(c for c in serial if c.isalnum())  # Remove noise
        
        # Smart extraction: If serial is too long, try to extract valid prefix+digits pattern
        if len(serial_clean) > self.pattern_serial_max and self.pattern_serial_allowed_prefixes:
            # Try to extract pattern: allowed_prefix + digits (up to max length)
            import re
            prefix_pattern = '|'.join(self.pattern_serial_allowed_prefixes)
            match = re.match(f'^([{prefix_pattern}])(\d+)', serial_clean, re.IGNORECASE)
            if match:
                extracted_serial = match.group(0)  # Get the matched part only
                if self.pattern_serial_min <= len(extracted_serial) <= self.pattern_serial_max:
                    logger.info(f"  [PATTERN] [SMART] Extracted '{extracted_serial}' from longer serial '{serial_clean}'")
                    serial_clean = extracted_serial
        
        if self.pattern_serial_min <= len(serial_clean) <= self.pattern_serial_max:
            score += 40
            
            # Strict validation if allowed prefixes are specified
            if self.pattern_serial_allowed_prefixes:
                # Check format: first char must be from allowed list, rest must be digits
                if len(serial_clean) > 0:
                    first_char = serial_clean[0].upper()
                    rest_chars = serial_clean[1:]
                    
                    # Validate first character
                    if first_char in self.pattern_serial_allowed_prefixes:
                        score += 30
                        logger.info(f"  [PATTERN] [OK] Serial prefix '{first_char}' valid (allowed: {', '.join(self.pattern_serial_allowed_prefixes)})")
                        
                        # Validate rest are digits
                        if rest_chars.isdigit():
                            digit_count = len(rest_chars)
                            score += 50
                            logger.info(f"  [PATTERN] [PERFECT] Serial format ({first_char} + {digit_count} digits)")
                            
                            # Bonus for ideal length (8-9 total = 1 letter + 7-8 digits)
                            if len(serial_clean) in [8, 9]:
                                score += 20
                                logger.info(f"  [PATTERN] [BONUS] Ideal length: {len(serial_clean)} chars")
                        else:
                            score -= 40
                            non_digit_count = sum(1 for c in rest_chars if not c.isdigit())
                            logger.info(f"  [PATTERN] [X] Serial has non-digit chars after prefix: {non_digit_count} invalid char(s)")
                    else:
                        score -= 40
                        logger.info(f"  [PATTERN] [X] Serial prefix '{first_char}' invalid (allowed: {', '.join(self.pattern_serial_allowed_prefixes)})")
            else:
                # Legacy validation (no strict prefix requirement)
                letter_count = sum(c.isalpha() for c in serial_clean)
                digit_count = sum(c.isdigit() for c in serial_clean)
                
                logger.info(f"  [PATTERN] [OK] Serial '{serial_clean}' valid ({len(serial_clean)} chars: {letter_count} letter(s), {digit_count} digit(s))")
                
                # Bonus for ideal format: 1 letter + 7-8 digits
                if letter_count == 1 and 7 <= digit_count <= 8:
                    score += 50
                    logger.info(f"  [PATTERN] [PERFECT] Serial format (1 letter + {digit_count} digits)")
                # Good format: mostly digits
                elif digit_count >= 7:
                    score += 30
                    logger.info(f"  [PATTERN] [OK] Good Serial format ({digit_count} digits)")
                # Acceptable format
                elif digit_count >= 6:
                    score += 10
                else:
                    score -= 10
                    logger.info(f"  [PATTERN] [WARN] Serial has few digits ({digit_count})")
            
            # Penalize trailing noise (space + single char)
            if serial != serial_clean:
                noise_chars = len(serial) - len(serial_clean)
                penalty = noise_chars * 15
                score -= penalty
                logger.info(f"  [PATTERN] [WARN] Trailing noise detected: '{serial}' (penalty: -{penalty})")
        else:
            score -= 30
            logger.info(f"  [PATTERN] [X] Serial '{serial_clean}' invalid length: {len(serial_clean)} (expected {self.pattern_serial_min}-{self.pattern_serial_max})")
        
        # Final score adjustment
        score = max(score, -1)  # Minimum score is -1 (invalid)
        
        logger.info(f"  [PATTERN] Total score: {score} for '{text}'")
        return score
    
    def _select_best_result_from_pages(self, all_results):
        """
        Select the best result from multiple pages using combined scoring
        
        Args:
            all_results: List of tuples (text, score, page_num, frequency_ratio)
            
        Returns:
            str: Best extracted text across all pages
        """
        logger.info(f"\n[MULTI-PAGE ANALYSIS] Analyzing results from {len(all_results)} page(s)...")
        
        # Aggregate results by text
        from collections import defaultdict
        aggregated = defaultdict(lambda: {'pages': [], 'scores': [], 'freq_ratios': []})
        
        for text, score, page_num, freq_ratio in all_results:
            aggregated[text]['pages'].append(page_num)
            aggregated[text]['scores'].append(score)
            aggregated[text]['freq_ratios'].append(freq_ratio)
        
        # Score each unique result
        final_scores = []
        for text, data in aggregated.items():
            # Calculate combined score
            avg_score = sum(data['scores']) / len(data['scores'])
            max_score = max(data['scores'])
            avg_freq_ratio = sum(data['freq_ratios']) / len(data['freq_ratios'])
            page_count = len(data['pages'])
            
            # Combined scoring:
            # - Average score (weight: 0.4)
            # - Max score (weight: 0.2)
            # - Average frequency ratio (weight: 0.3)
            # - Page count bonus (weight: 0.1)
            combined_score = (
                avg_score * 0.4 +
                max_score * 0.2 +
                avg_freq_ratio * 100 * 0.3 +  # Convert ratio to score range
                page_count * 10 * 0.1
            )
            
            # Additional penalty for trailing space + single char (likely OCR noise)
            if len(text) > 2 and text[-2] == ' ' and (text[-1].isalpha() or text[-1].isdigit()):
                combined_score -= 30
                logger.info(f"  [PENALTY] Trailing char detected in '{text}', -30 score")
            
            final_scores.append({
                'text': text,
                'combined_score': combined_score,
                'avg_score': avg_score,
                'max_score': max_score,
                'avg_freq_ratio': avg_freq_ratio,
                'page_count': page_count,
                'pages': data['pages']
            })
        
        # Sort by combined score (descending)
        final_scores.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Log analysis
        logger.info("\n[RESULT COMPARISON]")
        for i, result in enumerate(final_scores, 1):
            logger.info(
                f"  {i}. '{result['text']}' "
                f"(combined: {result['combined_score']:.1f}, "
                f"avg_score: {result['avg_score']:.1f}, "
                f"freq: {result['avg_freq_ratio']:.2f}, "
                f"pages: {result['page_count']}, "
                f"from: {result['pages']})"
            )
        
        best_result = final_scores[0]['text']
        logger.info(f"\n[FINAL DECISION] Selected: '{best_result}' (combined score: {final_scores[0]['combined_score']:.1f})")
        
        # Apply smart serial extraction to final result
        best_result = self._apply_smart_serial_extraction(best_result)
        if best_result != final_scores[0]['text']:
            logger.info(f"[SMART CLEAN] Cleaned result: '{best_result}'")
        
        return best_result
    
    def _apply_smart_serial_extraction(self, text):
        """
        Apply smart extraction to remove noise from serial number
        
        Args:
            text: Full text pattern (e.g., 'P-F-W1A-S17995875COA2')
            
        Returns:
            str: Cleaned text (e.g., 'P-F-W1A-S17995875')
        """
        if not text or not self.pattern_serial_allowed_prefixes:
            return text
        
        parts = text.split(self.expected_separator)
        if len(parts) != self.expected_parts:
            return text
        
        # Check if last part (serial) is too long
        serial = parts[3].strip()
        serial_clean = ''.join(c for c in serial if c.isalnum())
        
        if len(serial_clean) > self.pattern_serial_max:
            # Extract valid pattern: allowed_prefix + digits
            import re
            prefix_pattern = '|'.join(self.pattern_serial_allowed_prefixes)
            match = re.match(f'^([{prefix_pattern}])(\d{{6,8}})', serial_clean, re.IGNORECASE)
            if match:
                extracted_serial = match.group(0)
                parts[3] = extracted_serial
                cleaned_text = self.expected_separator.join(parts)
                logger.info(f"  [SMART EXTRACT] '{serial_clean}' -> '{extracted_serial}'")
                return cleaned_text
        
        return text
    
    def _try_multiple_ocr_methods(self, img, original_filename="", page_num=1):
        """
        Try multiple preprocessing methods to extract text
        Uses parallel processing for speed improvement
        
        Args:
            img: PIL Image object
            original_filename: Original PDF filename (for debug image naming)
            page_num: Page number (for debug image naming)
            
        Returns:
            tuple: (best_text, method_results_dict, frequency_ratio)
                - best_text: Best extracted text
                - method_results_dict: Dictionary with all method results and scores
                - frequency_ratio: Ratio of methods that agreed on best result (0.0-1.0)
        """
        self._current_debug_filename = original_filename
        self._current_debug_page = page_num
        results = []
        method_results = {}
        
        # Convert PIL to OpenCV format (shared across all methods)
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Apply black text filtering if enabled (to ignore colored text/watermarks)
        if self.ocr_filter_black_text:
            # Keep only dark text (below threshold), make everything else white
            _, gray = cv2.threshold(gray, self.ocr_black_threshold, 255, cv2.THRESH_TOZERO)
            logger.info(f"[OCR] Applied black text filter (threshold: {self.ocr_black_threshold})")
        
        # Tesseract config for single line with specific characters
        custom_config = '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        
        # Define all methods with their execution functions
        method_functions = {
            'method0': self._method0_hough,
            'method0B': self._method0B_contrast,
            'method0C': self._method0C_opening,
            'method7': self._method7_median,
            'method1': self._method1_lineremoval,
            'method2': self._method2_threshold,
            'method3': self._method3_adaptive,
            'method4': self._method4_otsu,
            'method5': self._method5_bilateral,
            'method6': self._method6_blackhat
        }
        
        if self.enable_parallel_processing:
            # PARALLEL EXECUTION - All methods run simultaneously
            logger.info(f"[PARALLEL] Running {len(self.method_priority)} methods in parallel (max {self.max_workers} workers)...")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all methods for parallel execution
                future_to_method = {
                    executor.submit(method_functions[method_name], gray, custom_config): method_name
                    for method_name in self.method_priority
                    if method_name in method_functions
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_method):
                    method_name = future_to_method[future]
                    try:
                        text, score = future.result()
                        method_results[method_name] = {'text': text, 'score': score}
                        
                        if text and len(text) > 3 and score >= 0:
                            results.append(text)
                            logger.info(f"  [OK] {method_name}: '{text}' (score: {score})")
                        else:
                            logger.info(f"  [SKIP] {method_name}: No valid result (score: {score})")
                            
                    except Exception as e:
                        logger.error(f"{method_name} failed: {e}")
                        method_results[method_name] = {'text': '', 'score': -1}
        else:
            # SEQUENTIAL EXECUTION - One method at a time
            logger.info("Running methods sequentially...")
            for method_name in self.method_priority:
                if method_name not in method_functions:
                    continue
                    
                try:
                    text, score = method_functions[method_name](gray, custom_config)
                    method_results[method_name] = {'text': text, 'score': score}
                    
                    if text and len(text) > 3 and score >= 0:
                        results.append(text)
                        logger.info(f"  [OK] {method_name}: '{text}' (score: {score})")
                    else:
                        logger.info(f"  [SKIP] {method_name}: No result (score: {score})")
                        
                except Exception as e:
                    logger.error(f"{method_name} failed: {e}")
                    method_results[method_name] = {'text': '', 'score': -1}
        
        logger.info(f"\n[STATS] Total results found: {len(results)}")
        
        # Analyze all results to find the best one
        if results:
            from collections import Counter
            frequency = Counter(results)
            logger.info(f"Result frequencies: {dict(frequency)}")
            
            # Score all unique results
            scored_results = []
            for text in set(results):
                score = self._validate_and_score_result(text)
                if score >= 0:
                    scored_results.append((score, frequency[text], text))
            
            if scored_results:
                # Sort by: 1) Score (desc), 2) Frequency (desc), 3) Length (asc)
                scored_results.sort(key=lambda x: (x[0], x[1], -len(x[2])), reverse=True)
                best_result = scored_results[0][2]
                best_score = scored_results[0][0]
                best_freq = scored_results[0][1]
                freq_ratio = best_freq / len(results)
                
                logger.info(f"\n[BEST] Best result: '{best_result}' (score: {best_score}, frequency: {best_freq}/{len(results)})")
                
                # Show top 3 alternatives if available
                if len(scored_results) > 1:
                    logger.info("Top alternatives:")
                    for i, (score, freq, text) in enumerate(scored_results[1:4], 2):
                        logger.info(f"  {i}. '{text}' (score: {score}, freq: {freq})")
                
                return best_result, method_results, freq_ratio
        
        logger.warning("[FAIL] No valid results from any method")
        return "", method_results, 0.0
    
    # ========== OCR Method Implementations ==========
    
    def _method2_threshold(self, gray, custom_config):
        """Method 2: High threshold for bold text (FAST)"""
        logger.info("[M2] Method 2 (high threshold)...")
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method2_threshold")
            if debug_path:
                cv2.imwrite(debug_path, thresh)
        text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 2: '{text}' (score: {score})")
        return text, score
    
    def _method3_adaptive(self, gray, custom_config):
        """Method 3: Adaptive threshold (FAST)"""
        logger.info("[M3] Method 3 (adaptive threshold)...")
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method3_adaptive")
            if debug_path:
                cv2.imwrite(debug_path, adaptive)
        text = pytesseract.image_to_string(adaptive, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 3: '{text}' (score: {score})")
        return text, score
    
    def _method4_otsu(self, gray, custom_config):
        """Method 4: OTSU with denoising (MEDIUM SPEED)"""
        logger.info("[M4] Method 4 (OTSU + denoise)...")
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method4_otsu")
            if debug_path:
                cv2.imwrite(debug_path, thresh)
        text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 4: '{text}' (score: {score})")
        return text, score
    
    def _method5_bilateral(self, gray, custom_config):
        """Method 5: Bilateral filter (MEDIUM SPEED)"""
        logger.info("[M5] Method 5 (bilateral filter)...")
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method5_bilateral")
            if debug_path:
                cv2.imwrite(debug_path, thresh)
        text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 5: '{text}' (score: {score})")
        return text, score
    
    def _method1_lineremoval(self, gray, custom_config):
        """Method 1: Line removal (MEDIUM SPEED)"""
        logger.info("[M1] Method 1 (line removal)...")
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        inverted = cv2.bitwise_not(binary)
        
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detect_horizontal = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        cnts = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        for c in cnts:
            cv2.drawContours(inverted, [c], -1, (0, 0, 0), 5)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opening = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=1)
        result = cv2.bitwise_not(opening)
        
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method1_lineremoval")
            if debug_path:
                cv2.imwrite(debug_path, result)
        text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 1: '{text}' (score: {score})")
        return text, score
    
    def _method6_blackhat(self, gray, custom_config):
        """Method 6: Black hat transform (FAST)"""
        logger.info("[M6] Method 6 (black hat)...")
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method6_blackhat")
            if debug_path:
                cv2.imwrite(debug_path, thresh)
        text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 6: '{text}' (score: {score})")
        return text, score
    
    def _method0B_contrast(self, gray, custom_config):
        """Method 0B: Contrast enhancement (MEDIUM SPEED)"""
        logger.info("[M0B] Method 0B (contrast + sharpen)...")
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        kernel_sharpen = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
        
        _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method0B_contrast")
            if debug_path:
                cv2.imwrite(debug_path, thresh)
        text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 0B: '{text}' (score: {score})")
        return text, score
    
    def _method0C_opening(self, gray, custom_config):
        """Method 0C: Morphological opening (FAST)"""
        logger.info("[M0C] Method 0C (opening)...")
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        result = cv2.dilate(opening, dilate_kernel, iterations=1)
        
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method0C_opening")
            if debug_path:
                cv2.imwrite(debug_path, result)
        text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 0C: '{text}' (score: {score})")
        return text, score
    
    def _method7_median(self, gray, custom_config):
        """Method 7: Median blur (FAST)"""
        logger.info("[M7] Method 7 (median blur)...")
        median = cv2.medianBlur(gray, 3)
        _, thresh = cv2.threshold(median, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        result = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method7_median")
            if debug_path:
                cv2.imwrite(debug_path, result)
        text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 7: '{text}' (score: {score})")
        return text, score
    
    def _method0_hough(self, gray, custom_config):
        """Method 0: Hough line removal (SLOW - for difficult cases)"""
        logger.info("[M0] Method 0 (Hough line removal)...")
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        edges = cv2.Canny(binary, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=5)
        
        line_mask = np.zeros_like(binary)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(line_mask, (x1, y1), (x2, y2), 255, 3)
        
        result = cv2.subtract(binary, line_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
        result = cv2.bitwise_not(result)
        
        if self.save_method_images:
            debug_path = self._get_debug_path(self._current_debug_filename, self._current_debug_page, "method0_hough")
            if debug_path:
                cv2.imwrite(debug_path, result)
        text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
        score = self._validate_and_score_result(text) if text else -1
        logger.info(f"  Method 0: '{text}' (score: {score})")
        return text, score
    
    def _send_extraction_log(self, original_filename, page_number, method_results, 
                            direct_text="", direct_score=None, final_answer="", 
                            debug_image_path="", status="success", error_message=""):
        """
        Send extraction log to API endpoint
        
        Args:
            original_filename: Original PDF filename
            page_number: Page number processed
            method_results: Dictionary with all OCR method results
            direct_text: Text extracted directly from PDF
            direct_score: Score for direct extraction
            final_answer: Final selected text
            debug_image_path: Path to debug image
            status: Processing status
            error_message: Error message if any
        """
        try:
            # Calculate direct_score if not provided
            if direct_score is None and direct_text:
                direct_score = self._validate_and_score_result(direct_text)
            elif direct_score is None:
                direct_score = 0
            
            # Prepare payload
            payload = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "original_filename": original_filename,
                "page_number": page_number,
                "method0_text": method_results.get('method0', {}).get('text', ''),
                "method0_score": method_results.get('method0', {}).get('score', 0),
                "method0B_text": method_results.get('method0B', {}).get('text', ''),
                "method0B_score": method_results.get('method0B', {}).get('score', 0),
                "method0C_text": method_results.get('method0C', {}).get('text', ''),
                "method0C_score": method_results.get('method0C', {}).get('score', 0),
                "method1_text": method_results.get('method1', {}).get('text', ''),
                "method1_score": method_results.get('method1', {}).get('score', 0),
                "method2_text": method_results.get('method2', {}).get('text', ''),
                "method2_score": method_results.get('method2', {}).get('score', 0),
                "method3_text": method_results.get('method3', {}).get('text', ''),
                "method3_score": method_results.get('method3', {}).get('score', 0),
                "method4_text": method_results.get('method4', {}).get('text', ''),
                "method4_score": method_results.get('method4', {}).get('score', 0),
                "method5_text": method_results.get('method5', {}).get('text', ''),
                "method5_score": method_results.get('method5', {}).get('score', 0),
                "method6_text": method_results.get('method6', {}).get('text', ''),
                "method6_score": method_results.get('method6', {}).get('score', 0),
                "method7_text": method_results.get('method7', {}).get('text', ''),
                "method7_score": method_results.get('method7', {}).get('score', 0),
                "direct_text": direct_text,
                "direct_score": direct_score,
                "status": status,
                "error_message": error_message,
                "debug_image_path": debug_image_path,
                "finnal_answer": final_answer  # Note: API uses "finnal_answer" (typo in API)
            }
            
            logger.info(f"Sending extraction log to API: {self.api_url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Send POST request with timeout
            response = requests.post(
                self.api_url,
                json=payload,
                headers={
                    'accept': '*/*',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            # Check response
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('success'):
                    logger.info(f"API log sent successfully. Log ID: {response_data.get('data', {}).get('log_id')}")
                else:
                    logger.warning(f"API returned success=false: {response_data.get('message')}")
            else:
                logger.warning(f"API request failed with status {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error("API request timed out after 10 seconds")
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to API at {self.api_url}")
        except Exception as e:
            logger.error(f"Failed to send extraction log to API: {e}", exc_info=True)
    
    def sanitize_filename(self, text, original_filename=None):
        """
        Convert extracted text to a valid filename
        
        Args:
            text: Extracted text
            original_filename: Original filename to use as fallback (without extension)
            
        Returns:
            str: Sanitized filename
        """
        if not text:
            # Use original filename if available, otherwise use "unnamed"
            if original_filename:
                logger.info(f"No text extracted, keeping original filename: {original_filename}")
                return original_filename
            return "unnamed"
        
        # Remove or replace invalid characters
        if self.config.getboolean('Settings', 'remove_special_chars', fallback=True):
            # Keep only alphanumeric, spaces, hyphens, and underscores
            text = re.sub(r'[^\w\s-]', '', text)
        
        # Replace spaces
        space_replacement = self.config.get('Settings', 'replace_spaces_with', fallback='_')
        text = text.replace(' ', space_replacement)
        
        # Remove multiple consecutive separators
        text = re.sub(r'[_-]+', '_', text)
        
        # Trim to max length
        max_length = self.config.getint('Settings', 'max_filename_length', fallback=100)
        text = text[:max_length]
        
        # Remove leading/trailing separators
        text = text.strip('_-')
        
        # If empty after sanitization, return default
        if not text:
            return "unnamed"
        
        return text
