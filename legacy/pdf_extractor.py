"""
PDF Text Extractor Module
Extracts text from specific regions of PDF files
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime
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
        
        # API logging configuration
        self.api_url = config.get('Settings', 'api_log_url', 
                                  fallback='http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog')
        self.enable_api_logging = config.getboolean('Settings', 'enable_api_logging', fallback=True)
        
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
            
            all_texts = []
            
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
                    all_texts.append(direct_text)
                    
                    # Log successful direct extraction to API
                    if self.enable_api_logging:
                        direct_score = self._validate_and_score_result(direct_text)
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
                    text = self._ocr_extract(page, header_rect, page_num, original_filename, direct_text)
                    if text:
                        all_texts.append(text)
            
            doc.close()
            
            # Combine texts from all pages
            if all_texts:
                # If multiple results, pick the longest one (most complete)
                final_text = max(all_texts, key=len)
                logger.info(f"Final extracted text: {final_text}")
                return final_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""
    
    def _ocr_extract(self, page, rect, page_num=1, original_filename="", direct_text=""):
        """
        Use OCR to extract text from a specific area
        
        Args:
            page: PyMuPDF page object
            rect: Rectangle area to extract
            page_num: Page number for debug logging
            original_filename: Original PDF filename for logging
            direct_text: Text extracted directly from PDF (if any)
            
        Returns:
            str: Extracted text via OCR
        """
        try:
            # Render the area as image at very high resolution (6x for better OCR)
            mat = fitz.Matrix(6, 6)  # 6x zoom for better OCR with bold text
            pix = page.get_pixmap(matrix=mat, clip=rect)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Save debug image to see what's being extracted
            debug_path = f"debug_page{page_num}_extracted_area.png"
            img.save(debug_path)
            logger.info(f"Debug: Saved extracted area to {debug_path}")
            
            # Try multiple preprocessing methods and get detailed results
            text, method_results = self._try_multiple_ocr_methods(img)
            
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
            
            return text
            
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
            
            return ""
    
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
    
    def _try_multiple_ocr_methods(self, img):
        """
        Try multiple preprocessing methods to extract text
        
        Args:
            img: PIL Image object
            
        Returns:
            tuple: (best_text, method_results_dict)
                - best_text: Best extracted text
                - method_results_dict: Dictionary with all method results and scores
        """
        results = []
        method_results = {}
        
        # Convert PIL to OpenCV format
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Tesseract config for single line with specific characters
        custom_config = '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        
        # Method 0: Advanced Line Removal with Hough Transform (NEW - BEST FOR SCRIBBLES)
        try:
            logger.info("Trying Method 0 (Hough line removal)...")
            
            # Threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Detect lines using Hough Line Transform
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=5)
            
            # Create mask for lines
            line_mask = np.zeros_like(binary)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Draw thick lines to remove
                    cv2.line(line_mask, (x1, y1), (x2, y2), 255, 3)
            
            # Remove lines from original
            result = cv2.subtract(binary, line_mask)
            
            # Clean up with morphology
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
            result = cv2.bitwise_not(result)
            
            cv2.imwrite("debug_method0_hough.png", result)
            text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method0'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 0 (Hough): {text}")
        except Exception as e:
            logger.error(f"Method 0 failed: {e}", exc_info=True)
            method_results['method0'] = {'text': '', 'score': -1}
        
        # Method 0B: Contrast enhancement with sharpening
        try:
            logger.info("Trying Method 0B (contrast + sharpen)...")
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Sharpen the image
            kernel_sharpen = np.array([[-1, -1, -1],
                                      [-1,  9, -1],
                                      [-1, -1, -1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
            
            # Apply threshold
            _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            cv2.imwrite("debug_method0B_contrast.png", thresh)
            text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method0B'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 0B (contrast): {text}")
        except Exception as e:
            logger.error(f"Method 0B failed: {e}", exc_info=True)
            method_results['method0B'] = {'text': '', 'score': -1}
        
        # Method 0C: Morphological opening with erosion-dilation
        try:
            logger.info("Trying Method 0C (morphological opening)...")
            
            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Apply threshold
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Morphological opening (erosion followed by dilation)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
            
            # Dilate slightly to make text bolder
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            result = cv2.dilate(opening, dilate_kernel, iterations=1)
            
            cv2.imwrite("debug_method0C_opening.png", result)
            text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method0C'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 0C (opening): {text}")
        except Exception as e:
            logger.error(f"Method 0C failed: {e}", exc_info=True)
            method_results['method0C'] = {'text': '', 'score': -1}
        
        # Method 7: Median blur with Otsu threshold
        try:
            logger.info("Trying Method 7 (median blur + Otsu)...")
            
            # Apply median blur to remove noise while preserving edges
            median = cv2.medianBlur(gray, 3)
            
            # Apply Otsu thresholding
            _, thresh = cv2.threshold(median, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Light morphological closing to connect broken characters
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
            result = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            cv2.imwrite("debug_method7_median.png", result)
            text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method7'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 7 (median): {text}")
        except Exception as e:
            logger.error(f"Method 7 failed: {e}", exc_info=True)
            method_results['method7'] = {'text': '', 'score': -1}
        
        # Method 1: Remove lines/scribbles using morphological operations
        try:
            logger.info("Trying Method 1 (line removal)...")
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            inverted = cv2.bitwise_not(binary)
            
            # Remove horizontal lines
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            detect_horizontal = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
            cnts = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            for c in cnts:
                cv2.drawContours(inverted, [c], -1, (0, 0, 0), 5)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            opening = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=1)
            result = cv2.bitwise_not(opening)
            
            cv2.imwrite("debug_method1_lineremoval.png", result)
            text = pytesseract.image_to_string(result, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method1'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 1 (line removal): {text}")
        except Exception as e:
            logger.error(f"Method 1 failed: {e}", exc_info=True)
            method_results['method1'] = {'text': '', 'score': -1}
        
        # Method 2: High threshold for bold text
        try:
            logger.info("Trying Method 2 (high threshold)...")
            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            cv2.imwrite("debug_method2_threshold.png", thresh)
            text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method2'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 2 (high threshold): {text}")
        except Exception as e:
            logger.error(f"Method 2 failed: {e}", exc_info=True)
            method_results['method2'] = {'text': '', 'score': -1}
        
        # Method 3: Adaptive threshold
        try:
            logger.info("Trying Method 3 (adaptive threshold)...")
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY, 11, 2)
            cv2.imwrite("debug_method3_adaptive.png", adaptive)
            text = pytesseract.image_to_string(adaptive, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method3'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 3 (adaptive): {text}")
        except Exception as e:
            logger.error(f"Method 3 failed: {e}", exc_info=True)
            method_results['method3'] = {'text': '', 'score': -1}
        
        # Method 4: OTSU with denoising
        try:
            logger.info("Trying Method 4 (OTSU)...")
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cv2.imwrite("debug_method4_otsu.png", thresh)
            text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method4'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 4 (OTSU): {text}")
        except Exception as e:
            logger.error(f"Method 4 failed: {e}", exc_info=True)
            method_results['method4'] = {'text': '', 'score': -1}
        
        # Method 5: Bilateral filter
        try:
            logger.info("Trying Method 5 (bilateral filter)...")
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cv2.imwrite("debug_method5_bilateral.png", thresh)
            text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method5'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 5 (bilateral): {text}")
        except Exception as e:
            logger.error(f"Method 5 failed: {e}", exc_info=True)
            method_results['method5'] = {'text': '', 'score': -1}
        
        # Method 6: Black Hat transform to find dark text
        try:
            logger.info("Trying Method 6 (black hat)...")
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
            blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
            _, thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cv2.imwrite("debug_method6_blackhat.png", thresh)
            text = pytesseract.image_to_string(thresh, lang='eng', config=custom_config).strip()
            score = self._validate_and_score_result(text) if text else -1
            method_results['method6'] = {'text': text, 'score': score}
            if text and len(text) > 3:
                results.append(text)
                logger.info(f"Method 6 (black hat): {text}")
        except Exception as e:
            logger.error(f"Method 6 failed: {e}", exc_info=True)
            method_results['method6'] = {'text': '', 'score': -1}
        
        logger.info(f"Total results found: {len(results)}")
        logger.info(f"All results: {results}")
        
        # Score and validate all results
        if results:
            logger.info("Scoring results based on format validation:")
            scored_results = []
            for text in results:
                score = self._validate_and_score_result(text)
                if score >= 0:
                    scored_results.append((score, text))
            
            if scored_results:
                # Count frequency of each result (for majority voting)
                from collections import Counter
                result_texts = [text for score, text in scored_results]
                frequency = Counter(result_texts)
                logger.info(f"Result frequencies: {dict(frequency)}")
                
                # Sort by:
                # 1. Score (highest first)
                # 2. Frequency/count (most common first) 
                # 3. Length (shorter is better, fewer errors)
                scored_results.sort(key=lambda x: (x[0], frequency[x[1]], -len(x[1])), reverse=True)
                
                best_result = scored_results[0][1]
                best_score = scored_results[0][0]
                best_frequency = frequency[best_result]
                
                logger.info(f"Best result selected: {best_result} (score: {best_score}, frequency: {best_frequency}/{len(results)})")
                return best_result, method_results
        
        logger.warning("No valid results from any method")
        return "", method_results
    
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
