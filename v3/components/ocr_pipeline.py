"""
OCR Pipeline - Simplified V3 that reuses V2 OCR methods
Adds V3 improvements: adaptive rendering, early exit, metrics integration
Adds PaddleOCR fallback when Tesseract conditions are not met
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Tuple, List, Optional
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
from v3.components.fallback_checker import FallbackChecker, create_fallback_checker_from_config
from v3.components.paddleocr_engine import PaddleOCREngine, get_paddleocr_engine

logger = logging.getLogger(__name__)


class OCRPipeline:
    """
    V3 OCR Pipeline - Improved version of V2 with:
    - Adaptive rendering (2x -> 3x -> 6x)
    - Early exit when score is good enough
    - Better metrics integration
    - Thread-safe (no shared state)
    - PaddleOCR fallback when Tesseract conditions are not met

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

        # Initialize PaddleOCR fallback (lazy loading)
        self._paddleocr_engine: Optional[PaddleOCREngine] = None
        self._fallback_checker: Optional[FallbackChecker] = None
        self._enable_paddleocr_fallback = config.enable_paddleocr_fallback
        self._enable_ensemble_voting = config.enable_ensemble_voting

        logger.info("OCR Pipeline V3.2 initialized (using V2 methods + PaddleOCR fallback)")

    def _get_fallback_checker(self) -> FallbackChecker:
        """Get or create FallbackChecker instance (lazy loading)"""
        if self._fallback_checker is None:
            self._fallback_checker = create_fallback_checker_from_config(self.config)
        return self._fallback_checker

    def _get_paddleocr_engine(self) -> Optional[PaddleOCREngine]:
        """Get or create PaddleOCR engine instance (lazy loading)"""
        if self._paddleocr_engine is None and self._enable_paddleocr_fallback:
            try:
                self._paddleocr_engine = get_paddleocr_engine(lang='en')
                if self._paddleocr_engine:
                    logger.info("PaddleOCR engine initialized for fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize PaddleOCR: {e}")
                self._paddleocr_engine = None
        return self._paddleocr_engine

    def _is_code_suspiciously_short(self, text: str) -> bool:
        """
        Check if code segment is suspiciously short (potential deletion error)

        Examples:
        - "R-HK-0AM-S18010861" -> code is "0AM" (3 chars, but starts with digit)
        - "R-HK-04AM-S18010861" -> code is "04AM" (4 chars, correct)

        Deletion error indicators:
        - Code is exactly at minimum length (2 chars)
        - Code starts with digit (0-9) and is short (might have lost a digit)
        - Code pattern looks like digit + letters (e.g., "0AM" instead of "04AM")

        Args:
            text: OCR result text

        Returns:
            True if code looks like it might have deletion error
        """
        if not text:
            return False

        parts = text.split(self.config.expected_separator)

        # Check 4-part format (B-HK-CODE-S123)
        if len(parts) == 4:
            code = parts[2]
            # Suspicious patterns:
            # 1. Code is at minimum length
            if len(code) == self.config.pattern_code_min:
                logger.debug(f"[Check] Code at minimum length: {code}")
                return True
            # 2. Code starts with digit and is short (might have lost a digit)
            if len(code) <= 3 and code and code[0].isdigit():
                logger.debug(f"[Check] Code starts with digit and is short: {code}")
                return True

        # Check 3-part format (B-CODE-S123)
        elif len(parts) == 3:
            code = parts[1]
            if len(code) <= 2:
                logger.debug(f"[Check] 3-part code too short: {code}")
                return True

        return False
    
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

        # Check for PaddleOCR fallback
        if self._enable_paddleocr_fallback:
            best_text, all_method_results, best_freq_ratio, fallback_info = \
                self._run_ocr_with_paddleocr_fallback(
                    img, context, best_text, all_method_results
                )
            logger.info(f"[OCR] Fallback info: {fallback_info}")

            # Re-score if fallback was used
            if "not_needed" not in fallback_info and "disabled" not in fallback_info:
                best_score, best_text = self.validator.validate_and_score(best_text)

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
        
        # Vote for best result using Validator Score + Frequency
        if results:
            frequency = Counter(results)

            # Score each unique result
            scored_results = []
            for text in set(results):
                score, corrected = self.validator.validate_and_score(text)
                freq = frequency[text]
                scored_results.append({
                    'text': text,
                    'corrected': corrected,
                    'score': score,
                    'frequency': freq
                })

            # Sort by: score first (higher is better), then by frequency (higher is better)
            scored_results.sort(key=lambda x: (x['score'], x['frequency']), reverse=True)

            best = scored_results[0]
            most_common_text = best['corrected'] if best['score'] > 0 else best['text']
            freq_ratio = best['frequency'] / len(results)

            logger.debug(f"OCR voting: best='{most_common_text}' (score={best['score']}, freq={best['frequency']})")
            return most_common_text, method_results, freq_ratio

        return "", method_results, 0.0

    def _get_low_confidence_chars(
        self,
        img,
        text: str,
        threshold: float = 70.0
    ) -> List[dict]:
        """
        Get characters with low confidence from Tesseract image_to_data

        This helps detect potential deletion/substitution errors by looking at
        per-character confidence levels.

        Args:
            img: OpenCV image (BGR)
            text: The OCR result text
            threshold: Confidence threshold (chars below this are flagged)

        Returns:
            List of dicts with low confidence character info:
            [{'char': '4', 'confidence': 45.0, 'position': 5}, ...]
        """
        import pytesseract
        import cv2
        from PIL import Image as PILImage

        try:
            # Convert to PIL
            pil_img = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

            # Get detailed data from Tesseract
            custom_config = '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
            data = pytesseract.image_to_data(pil_img, config=custom_config, output_type=pytesseract.Output.DICT)

            low_conf_chars = []

            # Extract characters with low confidence
            for i, (char, conf) in enumerate(zip(data['text'], data['conf'])):
                if char.strip() and conf > 0 and conf < threshold:
                    low_conf_chars.append({
                        'char': char,
                        'confidence': float(conf),
                        'position': i
                    })

            if low_conf_chars:
                logger.debug(f"[Confidence] Low confidence chars: {low_conf_chars}")

            return low_conf_chars

        except Exception as e:
            logger.error(f"[Confidence] Error getting char confidence: {e}")
            return []

    def _run_ocr_with_paddleocr_fallback(
        self,
        img: Image.Image,
        context: OCRContext,
        tesseract_text: str,
        tesseract_method_results: Dict
    ) -> Tuple[str, Dict, float, str]:
        """
        Run OCR with PaddleOCR fallback when conditions are not met

        Args:
            img: PIL Image
            context: OCR context
            tesseract_text: Result from Tesseract
            tesseract_method_results: Method results from Tesseract

        Returns:
            Tuple: (best_text, all_method_results, freq_ratio, fallback_info)
        """
        import cv2
        import numpy as np

        fallback_info = "none"

        # Check if PaddleOCR fallback is enabled
        if not self._enable_paddleocr_fallback:
            return tesseract_text, tesseract_method_results, 0.0, "disabled"

        # If validator score is already good/excellent, skip fallback.
        # This prevents unnecessary PaddleOCR calls when Tesseract output is usable
        # but fails a strict regex profile.
        base_score, _ = self.validator.validate_and_score(tesseract_text)
        if base_score >= self.config.score_threshold_for_escalation:
            logger.debug(
                f"[OCR] Skip PaddleOCR fallback: validator score already good ({base_score})"
            )
            return tesseract_text, tesseract_method_results, 0.0, f"not_needed(score={base_score})"

        # Calculate Tesseract confidence
        tesseract_confidence = self._calculate_tesseract_confidence(tesseract_method_results)

        # Check if we should use PaddleOCR fallback
        checker = self._get_fallback_checker()
        should_fallback, reason = checker.should_fallback(
            tesseract_text,
            tesseract_confidence,
            tesseract_char_data=None
        )

        if not should_fallback:
            logger.debug(f"[OCR] Tesseract result passed all checks, no fallback needed")
            return tesseract_text, tesseract_method_results, 0.0, "not_needed"

        logger.info(f"[OCR] Fallback triggered: {reason}")

        # Get PaddleOCR engine
        paddle_engine = self._get_paddleocr_engine()
        if paddle_engine is None:
            logger.warning("[OCR] PaddleOCR not available, using Tesseract result")
            return tesseract_text, tesseract_method_results, 0.0, "paddleocr_unavailable"

        # Run PaddleOCR
        try:
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            paddle_text, paddle_conf = paddle_engine.extract_text(img_cv)

            if not paddle_text:
                logger.warning("[OCR] PaddleOCR returned empty result")
                return tesseract_text, tesseract_method_results, 0.0, "paddleocr_empty"

            logger.info(f"[OCR] PaddleOCR result: '{paddle_text}' (confidence: {paddle_conf:.1f}%)")

            # Add to method results
            all_method_results = dict(tesseract_method_results)
            all_method_results['paddleocr'] = {'text': paddle_text, 'confidence': paddle_conf}

            # Ensemble voting if enabled
            if self._enable_ensemble_voting:
                best_text = self._ensemble_vote(
                    tesseract_text,
                    paddle_text,
                    tesseract_confidence,
                    paddle_conf
                )
                fallback_info = f"ensemble({reason})"
            else:
                # Use PaddleOCR result if it has higher confidence
                if paddle_conf > tesseract_confidence:
                    best_text = paddle_text
                    fallback_info = f"paddleocr_won({reason})"
                else:
                    best_text = tesseract_text
                    fallback_info = f"tesseract_won({reason})"

            return best_text, all_method_results, 0.0, fallback_info

        except Exception as e:
            logger.error(f"[OCR] PaddleOCR fallback failed: {e}")
            return tesseract_text, tesseract_method_results, 0.0, f"error({e})"

    def _calculate_tesseract_confidence(self, method_results: Dict) -> float:
        """Calculate average confidence from Tesseract method results"""
        if not method_results:
            return 0.0

        scores = [r.get('score', 0) for r in method_results.values() if isinstance(r, dict)]
        if not scores:
            return 0.0

        # Convert scores to approximate confidence (score is 0-150+)
        # Normalize to 0-100 range
        avg_score = sum(scores) / len(scores)
        confidence = min(100, max(0, avg_score / 1.5))

        return confidence

    def _ensemble_vote(
        self,
        tesseract_text: str,
        paddle_text: str,
        tesseract_conf: float,
        paddle_conf: float
    ) -> str:
        """
        Vote between Tesseract and PaddleOCR results

        Strategy:
        1. If both results are identical, return either
        2. Validate both results and use the one with higher score
        3. Weight by confidence

        Args:
            tesseract_text: Text from Tesseract
            paddle_text: Text from PaddleOCR
            tesseract_conf: Tesseract confidence (0-100)
            paddle_conf: PaddleOCR confidence (0-100)

        Returns:
            Best text result
        """
        # If identical, return either
        if tesseract_text == paddle_text:
            logger.debug("[Ensemble] Both engines returned identical result")
            return tesseract_text

        # Validate and score both results
        tess_score, tess_corrected = self.validator.validate_and_score(tesseract_text)
        paddle_score, paddle_corrected = self.validator.validate_and_score(paddle_text)

        logger.debug(f"[Ensemble] Tesseract: '{tess_corrected}' (score={tess_score}, conf={tesseract_conf:.1f}%)")
        logger.debug(f"[Ensemble] PaddleOCR: '{paddle_corrected}' (score={paddle_score}, conf={paddle_conf:.1f}%)")

        # Use weighted decision
        # Weight: 60% validation score + 40% confidence
        tess_weighted = (tess_score * 0.6) + (tesseract_conf * 0.4)
        paddle_weighted = (paddle_score * 0.6) + (paddle_conf * 0.4)

        if paddle_weighted > tess_weighted:
            logger.info(f"[Ensemble] Selected PaddleOCR result (weighted: {paddle_weighted:.1f} vs {tess_weighted:.1f})")
            return paddle_corrected
        else:
            logger.info(f"[Ensemble] Selected Tesseract result (weighted: {tess_weighted:.1f} vs {paddle_weighted:.1f})")
            return tess_corrected
