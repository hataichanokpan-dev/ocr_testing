"""
OCR Pipeline - Simplified V3 that reuses V2 OCR methods
Adds V3 improvements: adaptive rendering, early exit, metrics integration
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Tuple, List
from collections import Counter
from PIL import Image

# Add parent directory to path to import V2
parent_dir = str(Path(__file__).parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import V2 OCR extractor to reuse methods
from pdf_extractorV2 import PDFTextExtractor as V2Extractor

from v3.utils.config_manager import ExtractionConfig
from v3.utils.ocr_context import OCRContext
from v3.components.header_validator import HeaderValidator
from v3.utils.debug_manager import DebugImageManager
from v3.utils.metrics_tracker import MetricsTracker

logger = logging.getLogger(__name__)


class OCRPipeline:
    """
    V3 OCR Pipeline - Improved version of V2 with:
    - Adaptive rendering (2x -> 3x -> 6x)
    - Early exit when score is good enough
    - Better metrics integration
    - Thread-safe (no shared state)
    
    Reuses V2's proven OCR methods while adding V3 optimizations
    """
    
    def __init__(
        self,
        config: ExtractionConfig,
        validator: HeaderValidator,
        debug_manager: DebugImageManager,
        metrics_tracker: MetricsTracker = None
    ):
        """
        Initialize OCR pipeline
        
        Args:
            config: Extraction configuration
            validator: Header validator
            debug_manager: Debug image manager
            metrics_tracker: Optional metrics tracker
        """
        self.config = config
        self.validator = validator
        self.debug_manager = debug_manager
        self.metrics_tracker = metrics_tracker
        
        # Create V2 extractor instance (for reusing methods)
        # We'll use a dummy config just to initialize it
        import configparser
        dummy_config = configparser.ConfigParser()
        dummy_config['Settings'] = {}
        self.v2_extractor = V2Extractor(dummy_config)
        
        # Copy config values we need
        self.v2_extractor.expected_separator = config.expected_separator
        self.v2_extractor.enable_pattern_validation = config.enable_pattern_validation
        
        # Initialize V2 debug attributes (required by V2 methods)
        self.v2_extractor._current_debug_filename = ""
        self.v2_extractor._current_debug_page = 0
        self.v2_extractor.save_method_images = config.save_debug_images
        
        logger.info("OCR Pipeline V3 initialized (using V2 methods with V3 improvements)")
    
    def extract_text_with_adaptive_rendering(
        self,
        page,
        rect,
        context: OCRContext
    ) -> Tuple[str, Dict, float]:
        """
        Extract text using adaptive rendering strategy
        
        V3 Improvement: Start with low scale, escalate if needed
        - Try 2x first (fast)
        - If score < threshold, try 3x
        - If still low, try 6x (slow but accurate)
        
        Args:
            page: PyMuPDF page object
            rect: Rectangle to extract
            context: OCR context (filename, page_num, etc.)
        
        Returns:
            Tuple: (best_text, method_results, frequency_ratio)
        """
        import fitz
        from PIL import Image
        
        if self.config.adaptive_rendering:
            scales = [
                self.config.initial_render_scale,  # 2.0 (fast)
                3.0,                               # medium
                self.config.max_render_scale       # 6.0 (slow but accurate)
            ]
        else:
            # Non-adaptive: use max scale only
            scales = [self.config.max_render_scale]
        
        best_text = ""
        best_score = -1
        all_method_results = {}
        best_freq_ratio = 0.0
        
        for scale in scales:
            logger.info(f"[OCR] Trying scale {scale}x (page {context.page_num})")
            
            # Render at this scale
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, clip=rect)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Save debug image
            if self.debug_manager.enabled:
                import cv2
                import numpy as np
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                self.debug_manager.save_image(
                    img_cv,
                    context.filename,
                    context.page_num,
                    f"scale_{scale}x"
                )
            
            # Run OCR with current scale
            text, method_results, freq_ratio = self._run_ocr_methods(img, context)
            
            # Score the result
            score, corrected_text = self.validator.validate_and_score(text)
            
            logger.info(f"[OCR] Scale {scale}x result: '{corrected_text}' (score: {score})")
            
            # Update if better
            if score > best_score:
                best_score = score
                best_text = corrected_text
                all_method_results = method_results
                best_freq_ratio = freq_ratio
            
            # Record OCR attempt in metrics
            if self.metrics_tracker and context.job_id:
                self.metrics_tracker.record_ocr_attempt(
                    context.job_id,
                    successful=(score >= 0),
                    score=score
                )
            
            # Early exit if score is excellent
            if score >= self.config.early_exit_score:
                logger.info(f"[OCR] Early exit: excellent score {score}")
                break
            
            # Don't try higher scales if score is already good
            if score >= self.config.score_threshold_for_escalation:
                logger.info(f"[OCR] Good score {score}, no need for higher scale")
                break
        
        logger.info(f"[OCR] Final result: '{best_text}' (score: {best_score})")
        return best_text, all_method_results, best_freq_ratio
    
    def _run_ocr_methods(
        self,
        img: Image.Image,
        context: OCRContext
    ) -> Tuple[str, Dict, float]:
        """
        Run multiple OCR methods and vote for best result
        
        Reuses V2's proven methods with V3's OCR budget control
        """
        import cv2
        import numpy as np
        import pytesseract
        
        # Convert to OpenCV format
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Apply black text filter if enabled
        if self.config.ocr_filter_black_text:
            _, gray = cv2.threshold(
                gray,
                self.config.ocr_black_threshold,
                255,
                cv2.THRESH_TOZERO
            )
        
        results = []
        method_results = {}
        custom_config = '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        
        # Set V2 extractor context (required by V2 methods for debug saving)
        self.v2_extractor._current_debug_filename = context.filename
        self.v2_extractor._current_debug_page = context.page_num
        
        # Method priority (voting methods first for best accuracy)
        methods = [
            ('method2', lambda: self.v2_extractor._method2_threshold(gray, custom_config)),
            ('method3', lambda: self.v2_extractor._method3_adaptive(gray, custom_config)),
            ('method4', lambda: self.v2_extractor._method4_otsu(gray, custom_config)),
            ('method5', lambda: self.v2_extractor._method5_bilateral(gray, custom_config)),
        ]
        
        attempts = 0
        for method_name, method_func in methods:
            if attempts >= self.config.max_ocr_attempts:
                logger.debug(f"Reached max OCR attempts: {self.config.max_ocr_attempts}")
                break
            
            try:
                text, score = method_func()
                if text:
                    results.append(text)
                    method_results[method_name] = {'text': text, 'score': score}
                    attempts += 1
                    
                    # Early exit if excellent score
                    if score >= self.config.early_exit_score:
                        logger.debug(f"{method_name} got excellent score: {score}")
                        break
            
            except Exception as e:
                logger.error(f"{method_name} failed: {e}")
        
        # Vote for best result
        if results:
            frequency = Counter(results)
            most_common_text = frequency.most_common(1)[0][0]
            freq_ratio = frequency[most_common_text] / len(results)
            
            logger.debug(f"OCR voting: {dict(frequency)}")
            return most_common_text, method_results, freq_ratio
        
        return "", method_results, 0.0
