"""
Image Processor - Image preprocessing methods for OCR
Extracted from V2 to separate concerns
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional
from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Image preprocessing utilities for OCR optimization
    
    Contains all image manipulation methods from V2:
    - Thresholding (simple, adaptive, OTSU)
    - Filtering (median, bilateral, Gaussian)
    - Morphological operations (opening, closing, black hat)
    - Line removal (Hough transform)
    - Enhancement (CLAHE, sharpening)
    """
    
    @staticmethod
    def apply_simple_threshold(gray: np.ndarray, threshold: int = 200) -> np.ndarray:
        """Simple binary threshold"""
        _, result = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        return result
    
    @staticmethod
    def apply_otsu_threshold(gray: np.ndarray, denoise: bool = False) -> np.ndarray:
        """OTSU threshold with optional denoising"""
        if denoise:
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, result = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return result
    
    @staticmethod
    def apply_adaptive_threshold(gray: np.ndarray, block_size: int = 11, c: int = 2) -> np.ndarray:
        """Adaptive threshold"""
        result = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size, c
        )
        return result
    
    @staticmethod
    def apply_bilateral_filter(gray: np.ndarray) -> np.ndarray:
        """Bilateral filter + OTSU"""
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        _, result = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return result
    
    @staticmethod
    def apply_median_blur(gray: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """Median blur + morphological closing"""
        median = cv2.medianBlur(gray, kernel_size)
        _, thresh = cv2.threshold(median, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        result = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        return result
    
    @staticmethod
    def apply_line_removal(gray: np.ndarray) -> np.ndarray:
        """Remove horizontal lines using morphology"""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        inverted = cv2.bitwise_not(binary)
        
        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detect_horizontal = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # Remove lines
        cnts = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        for c in cnts:
            cv2.drawContours(inverted, [c], -1, (0, 0, 0), 5)
        
        # Clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opening = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel, iterations=1)
        result = cv2.bitwise_not(opening)
        
        return result
    
    @staticmethod
    def apply_black_hat(gray: np.ndarray) -> np.ndarray:
        """Black hat morphological transform"""
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, result = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return result
    
    @staticmethod
    def apply_contrast_enhancement(gray: np.ndarray) -> np.ndarray:
        """CLAHE + sharpening"""
        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Sharpen
        kernel_sharpen = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
        
        _, result = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return result
    
    @staticmethod
    def apply_morphological_opening(gray: np.ndarray) -> np.ndarray:
        """Morphological opening"""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        result = cv2.dilate(opening, dilate_kernel, iterations=1)
        
        return result
    
    @staticmethod
    def apply_hough_line_removal(gray: np.ndarray) -> np.ndarray:
        """Advanced line removal using Hough transform (slow)"""
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        edges = cv2.Canny(binary, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=5)
        
        line_mask = np.zeros_like(binary)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(line_mask, (x1, y1), (x2, y2), (255, 255, 255), 2)
        
        result = cv2.subtract(binary, line_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
        result = cv2.bitwise_not(result)
        
        return result
    
    @staticmethod
    def filter_black_text(gray: np.ndarray, threshold: int = 100) -> np.ndarray:
        """Keep only black text (remove colored text/watermarks)"""
        _, result = cv2.threshold(gray, threshold, 255, cv2.THRESH_TOZERO)
        return result
    
    @staticmethod
    def pil_to_cv2(pil_image: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert PIL Image to OpenCV format
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (color image, grayscale image)
        """
        img_cv = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        return img_cv, gray
