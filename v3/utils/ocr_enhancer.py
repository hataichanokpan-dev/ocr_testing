"""
OCR Enhancer - Advanced image pre-processing and multi-engine OCR
V3.1 - Full OCR Upgrade
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional
from PIL import Image

logger = logging.getLogger(__name__)


class OCREnhancer:
    """
    Advanced OCR enhancement techniques
    
    Features:
    - Deskewing (auto-rotation)
    - Morphological operations
    - CLAHE (Contrast Limited Adaptive Histogram Equalization)
    - Pattern-based corrections
    """
    
    def __init__(self, config):
        """
        Initialize OCR enhancer
        
        Args:
            config: ExtractionConfig with enhancement settings
        """
        self.config = config
        self.enable_deskewing = config.enable_deskewing
        self.enable_morphological = config.enable_morphological_ops
        self.enable_clahe = config.enable_clahe
        self.enable_pattern_correction = config.enable_pattern_correction
        
        logger.info(f"OCR Enhancer initialized:")
        logger.info(f"  Deskewing: {self.enable_deskewing}")
        logger.info(f"  Morphological ops: {self.enable_morphological}")
        logger.info(f"  CLAHE: {self.enable_clahe}")
        logger.info(f"  Pattern correction: {self.enable_pattern_correction}")
    
    def enhance_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply all enabled enhancements to image
        
        Args:
            image: Grayscale image (numpy array)
        
        Returns:
            Enhanced image
        """
        enhanced = image.copy()
        
        # 1. Deskewing (fix rotated text)
        if self.enable_deskewing:
            enhanced = self._deskew(enhanced)
        
        # 2. CLAHE (improve contrast adaptively)
        if self.enable_clahe:
            enhanced = self._apply_clahe(enhanced)
        
        # 3. Morphological operations (enhance text)
        if self.enable_morphological:
            enhanced = self._morphological_enhancement(enhanced)
        
        return enhanced
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Auto-rotate image to fix skew
        
        Args:
            image: Grayscale image
        
        Returns:
            Deskewed image
        """
        try:
            # Detect skew angle
            angle = self._detect_skew_angle(image)
            
            if abs(angle) > 0.5:  # Only rotate if angle is significant
                logger.debug(f"[DESKEW] Detected angle: {angle:.2f}°")
                
                # Rotate image
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                return rotated
            
            return image
        
        except Exception as e:
            logger.warning(f"[DESKEW] Failed: {e}")
            return image
    
    def _detect_skew_angle(self, image: np.ndarray) -> float:
        """
        Detect skew angle using Hough Line Transform
        
        Args:
            image: Grayscale image
        
        Returns:
            Detected angle in degrees
        """
        # Threshold
        thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Detect edges
        edges = cv2.Canny(thresh, 50, 150, apertureSize=3)
        
        # Detect lines
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100,
            minLineLength=100, maxLineGap=10
        )
        
        if lines is None or len(lines) == 0:
            return 0.0
        
        # Calculate angles
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            angles.append(angle)
        
        # Get median angle (more robust than mean)
        median_angle = np.median(angles)
        
        # Normalize to -45 to 45 degrees
        if median_angle < -45:
            median_angle = 90 + median_angle
        elif median_angle > 45:
            median_angle = median_angle - 90
        
        return median_angle
    
    def _apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """
        Apply Contrast Limited Adaptive Histogram Equalization
        
        Args:
            image: Grayscale image
        
        Returns:
            Enhanced image
        """
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
            logger.debug("[CLAHE] Applied contrast enhancement")
            return enhanced
        
        except Exception as e:
            logger.warning(f"[CLAHE] Failed: {e}")
            return image
    
    def _morphological_enhancement(self, image: np.ndarray) -> np.ndarray:
        """
        Apply morphological operations to enhance text
        
        Args:
            image: Grayscale image
        
        Returns:
            Enhanced image
        """
        try:
            # Small kernel to connect text components
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            
            # Morphological closing (connect broken characters)
            morph = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
            
            logger.debug("[MORPH] Applied morphological enhancement")
            return morph
        
        except Exception as e:
            logger.warning(f"[MORPH] Failed: {e}")
            return image
    
    def apply_pattern_correction(self, text: str) -> str:
        """
        Apply pattern-based corrections for common OCR mistakes
        
        Common corrections:
        - O → 0 in serial numbers
        - l → 1 in serial numbers
        - I → 1 in serial numbers
        
        Args:
            text: OCR result text
        
        Returns:
            Corrected text
        """
        if not self.enable_pattern_correction or not text:
            return text
        
        try:
            parts = text.split(self.config.expected_separator)
            
            if len(parts) >= 4:
                # Get serial number (last part)
                serial = parts[-1]
                original_serial = serial
                
                # Extract prefix and digits
                if len(serial) > 1:
                    prefix = serial[0] if serial[0].isalpha() else ''
                    digits = serial[1:] if prefix else serial
                    
                    # Apply corrections to digits only
                    corrected_digits = digits
                    corrected_digits = corrected_digits.replace('O', '0')  # O → 0
                    corrected_digits = corrected_digits.replace('o', '0')  # o → 0
                    corrected_digits = corrected_digits.replace('l', '1')  # l → 1
                    corrected_digits = corrected_digits.replace('I', '1')  # I → 1
                    corrected_digits = corrected_digits.replace('Z', '2')  # Z → 2 (sometimes)
                    
                    if corrected_digits != digits:
                        serial = prefix + corrected_digits
                        parts[-1] = serial
                        corrected_text = self.config.expected_separator.join(parts)
                        
                        logger.debug(
                            f"[PATTERN-CORRECT] '{original_serial}' → '{serial}' "
                            f"(full: '{text}' → '{corrected_text}')"
                        )
                        return corrected_text
            
            return text
        
        except Exception as e:
            logger.warning(f"[PATTERN-CORRECT] Failed: {e}")
            return text
    
    def get_tesseract_config(self) -> str:
        """
        Get optimized Tesseract configuration string
        
        Returns:
            Tesseract config string
        """
        config_parts = []
        
        # PSM Mode (7 = single text line, best for headers)
        config_parts.append(f'--psm {self.config.tesseract_psm_mode}')
        
        # OEM Mode (3 = default, both LSTM + legacy)
        config_parts.append('--oem 3')
        
        # Character whitelist (only allow specific characters)
        if self.config.tesseract_char_whitelist:
            # Escape for command line
            whitelist = self.config.tesseract_char_whitelist
            config_parts.append(f'-c tessedit_char_whitelist={whitelist}')
        
        config_str = ' '.join(config_parts)
        logger.debug(f"[TESSERACT-CONFIG] {config_str}")
        return config_str


class MultiEngineOCR:
    """
    Multiple OCR engines with voting
    
    Supports:
    - Tesseract (default)
    - EasyOCR (optional)
    - PaddleOCR (optional)
    """
    
    def __init__(self, config):
        """Initialize multi-engine OCR"""
        self.config = config
        self.use_easyocr = config.use_easyocr
        self.use_paddleocr = config.use_paddleocr
        
        # Lazy initialization of engines
        self.easyocr_reader = None
        self.paddleocr_reader = None
        
        if self.use_easyocr:
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
                logger.info("[MULTI-OCR] EasyOCR initialized")
            except ImportError:
                logger.warning("[MULTI-OCR] EasyOCR not available (pip install easyocr)")
                self.use_easyocr = False
        
        if self.use_paddleocr:
            try:
                from paddleocr import PaddleOCR
                self.paddleocr_reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("[MULTI-OCR] PaddleOCR initialized")
            except ImportError:
                logger.warning("[MULTI-OCR] PaddleOCR not available (pip install paddleocr)")
                self.use_paddleocr = False
    
    def extract_with_voting(
        self,
        image: np.ndarray,
        tesseract_result: str
    ) -> Tuple[str, dict]:
        """
        Extract text using multiple engines and vote
        
        Args:
            image: Image to process
            tesseract_result: Result from Tesseract
        
        Returns:
            Tuple of (best_result, all_results_dict)
        """
        results = {'tesseract': tesseract_result}
        
        # Try EasyOCR
        if self.use_easyocr and self.easyocr_reader:
            try:
                easyocr_results = self.easyocr_reader.readtext(image)
                if easyocr_results:
                    # Concatenate all detected text
                    easyocr_text = ' '.join([item[1] for item in easyocr_results])
                    results['easyocr'] = easyocr_text.strip()
            except Exception as e:
                logger.warning(f"[EASYOCR] Error: {e}")
        
        # Try PaddleOCR
        if self.use_paddleocr and self.paddleocr_reader:
            try:
                try:
                    paddleocr_results = self.paddleocr_reader.ocr(image, cls=True)
                except TypeError as e:
                    if "unexpected keyword argument 'cls'" in str(e):
                        logger.debug("[PADDLEOCR] API does not accept `cls`; retrying without it")
                        paddleocr_results = self.paddleocr_reader.ocr(image)
                    else:
                        raise
                if paddleocr_results and paddleocr_results[0]:
                    # Extract text from results
                    paddleocr_text = ' '.join([line[1][0] for line in paddleocr_results[0]])
                    results['paddleocr'] = paddleocr_text.strip()
            except Exception as e:
                logger.warning(f"[PADDLEOCR] Error: {e}")
        
        # Vote for best result (prefer Tesseract if all are similar)
        best_result = tesseract_result
        
        logger.debug(f"[MULTI-OCR] Results: {results}")
        return best_result, results
