"""
OCR Pipeline - V3 OCR orchestration
Adds V3 improvements: adaptive rendering, early exit, metrics integration
Adds PaddleOCR fallback when Tesseract conditions are not met
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from collections import Counter, defaultdict
from PIL import Image

from v3.utils.config_manager import ExtractionConfig
from v3.utils.ocr_context import OCRContext
from v3.utils.ocr_enhancer import OCREnhancer
from v3.components.header_validator import HeaderValidator
from v3.utils.debug_manager import DebugImageManager
from v3.utils.metrics_tracker import MetricsTracker
from v3.components.fallback_checker import FallbackChecker, create_fallback_checker_from_config
from v3.components.paddleocr_engine import PaddleOCREngine, get_paddleocr_engine

logger = logging.getLogger(__name__)


class OCRPipeline:
    """
    V3 OCR Pipeline with:
    - Adaptive rendering (2x -> 3x -> 6x)
    - Early exit when score is good enough
    - Better metrics integration
    - Thread-safe (no shared state)
    - PaddleOCR fallback when Tesseract conditions are not met
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
        self.ocr_enhancer = OCREnhancer(config)

        # Initialize PaddleOCR fallback (lazy loading)
        self._paddleocr_engine: Optional[PaddleOCREngine] = None
        self._fallback_checker: Optional[FallbackChecker] = None
        self._enable_paddleocr_fallback = config.enable_paddleocr_fallback
        self._enable_ensemble_voting = config.enable_ensemble_voting
        self._tesseract_available = self._configure_tesseract()

        logger.info("OCR Pipeline V3.2 initialized (native V3 methods + PaddleOCR fallback)")

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

    def _configure_tesseract(self) -> bool:
        """
        Configure and verify Tesseract executable path.

        Resolution order:
        1) `tesseract_cmd` in config.ini
        2) `TESSERACT_CMD` environment variable
        3) `tesseract` from PATH
        4) Common Windows install paths
        """
        import pytesseract

        candidate_paths: List[str] = []

        config_cmd = (getattr(self.config, "tesseract_cmd", "") or "").strip()
        if config_cmd:
            candidate_paths.append(config_cmd)

        env_cmd = os.environ.get("TESSERACT_CMD", "").strip()
        if env_cmd:
            candidate_paths.append(env_cmd)

        path_cmd = shutil.which("tesseract")
        if path_cmd:
            candidate_paths.append(path_cmd)

        if os.name == "nt":
            candidate_paths.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ])

        seen = set()
        resolved_candidates = []
        for cmd in candidate_paths:
            if not cmd:
                continue
            if cmd.lower() in seen:
                continue
            seen.add(cmd.lower())
            resolved_candidates.append(cmd)

        for cmd in resolved_candidates:
            if Path(cmd).exists() or cmd.lower() == "tesseract":
                try:
                    pytesseract.pytesseract.tesseract_cmd = cmd
                    _ = pytesseract.get_tesseract_version()
                    logger.info(f"Tesseract configured: {cmd}")
                    return True
                except Exception:
                    continue

        logger.error(
            "Tesseract is not available. Set `tesseract_cmd` in v3/config.ini "
            "or install Tesseract and add it to PATH."
        )
        return False

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
        
        Runs native V3 OCR methods with budget control
        """
        import cv2
        import numpy as np

        if not self._tesseract_available:
            return "", {'tesseract': {'text': '', 'score': -1, 'error': 'tesseract_not_available'}}, 0.0
        
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
        
        results: List[str] = []
        method_results: Dict[str, Dict] = {}
        text_confidences: Dict[str, List[float]] = defaultdict(list)

        tesseract_configs = self._get_tesseract_configs()
        methods = [
            ("method2", self._method2_threshold),
            ("method3", self._method3_adaptive),
            ("method4", self._method4_otsu),
            ("method5", self._method5_bilateral),
        ]

        attempts = 0
        early_exit = False
        for psm_mode, custom_config in tesseract_configs:
            for method_name, method_func in methods:
                if attempts >= self.config.max_ocr_attempts:
                    logger.debug(f"Reached max OCR attempts: {self.config.max_ocr_attempts}")
                    break

                method_key = f"{method_name}_psm{psm_mode}"
                try:
                    text, score, confidence = method_func(gray, custom_config, context)
                    attempts += 1

                    if text:
                        results.append(text)
                        text_confidences[text].append(confidence)
                        method_results[method_key] = {
                            "text": text,
                            "score": score,
                            "confidence": confidence,
                            "psm_mode": psm_mode,
                        }

                        # Early exit only when structure score + OCR confidence are both strong.
                        if (
                            score >= self.config.early_exit_score
                            and confidence >= self.config.tesseract_confidence_threshold
                        ):
                            logger.debug(
                                f"{method_key} got excellent result (score={score}, conf={confidence:.1f}%)"
                            )
                            early_exit = True
                            break
                    else:
                        method_results[method_key] = {
                            "text": "",
                            "score": -1,
                            "confidence": confidence,
                            "psm_mode": psm_mode,
                        }

                except Exception as e:
                    logger.error(f"{method_key} failed: {e}")

            if early_exit or attempts >= self.config.max_ocr_attempts:
                break

        # Vote for best result using validator score + confidence + frequency
        if results:
            frequency = Counter(results)
            scored_results = []
            for text in set(results):
                score, corrected = self.validator.validate_and_score(text)
                freq = frequency[text]
                conf_values = text_confidences.get(text, [])
                avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0
                weighted = (score * 0.7) + (avg_conf * 0.3)
                scored_results.append({
                    "text": text,
                    "corrected": corrected,
                    "score": score,
                    "frequency": freq,
                    "avg_confidence": avg_conf,
                    "weighted": weighted,
                })

            scored_results.sort(
                key=lambda x: (x["weighted"], x["score"], x["frequency"], x["avg_confidence"]),
                reverse=True,
            )

            best = scored_results[0]
            most_common_text = best["corrected"] if best["score"] > 0 else best["text"]
            freq_ratio = best["frequency"] / len(results)

            logger.debug(
                f"OCR voting: best='{most_common_text}' "
                f"(score={best['score']}, conf={best['avg_confidence']:.1f}%, freq={best['frequency']})"
            )
            return most_common_text, method_results, freq_ratio

        return "", method_results, 0.0

    def _get_tesseract_configs(self) -> List[Tuple[int, str]]:
        """Build Tesseract config variants (multi-PSM) for better per-page reading."""
        whitelist = self.config.tesseract_char_whitelist or "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        psm_modes = [self.config.tesseract_psm_mode, 6, 7, 13]
        seen = set()
        variants: List[Tuple[int, str]] = []
        for psm in psm_modes:
            if psm in seen:
                continue
            seen.add(psm)
            config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist={whitelist}"
            variants.append((psm, config))
        return variants

    def _ocr_text_and_confidence(self, image, custom_config: str) -> Tuple[str, float]:
        """Run OCR and estimate confidence from Tesseract per-token data."""
        import pytesseract

        text = pytesseract.image_to_string(image, lang="eng", config=custom_config).strip()
        if not text:
            return "", 0.0

        confidence_values: List[float] = []
        try:
            data = pytesseract.image_to_data(
                image,
                lang="eng",
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )
            for raw_conf in data.get("conf", []):
                try:
                    conf = float(raw_conf)
                except Exception:
                    continue
                if conf >= 0:
                    confidence_values.append(conf)
        except Exception:
            pass

        avg_conf = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        return text, avg_conf

    def _save_method_debug_image(
        self,
        image,
        context: OCRContext,
        method_name: str
    ) -> None:
        """Save OCR method output image if method-image debug is enabled."""
        if self.config.save_method_images and self.debug_manager.enabled:
            self.debug_manager.save_image(image, context.filename, context.page_num, method_name)

    def _method2_threshold(
        self,
        gray,
        custom_config: str,
        context: OCRContext
    ) -> Tuple[str, int, float]:
        """Method 2: Enhanced thresholding with V3 pre-processing."""
        import cv2

        processed = self.ocr_enhancer.enhance_image(gray)
        _, thresh = cv2.threshold(processed, 200, 255, cv2.THRESH_BINARY)
        self._save_method_debug_image(thresh, context, "method2_threshold")

        text, confidence = self._ocr_text_and_confidence(thresh, custom_config)
        text = self.ocr_enhancer.apply_pattern_correction(text)
        score, corrected = self.validator.validate_and_score(text) if text else (-1, "")
        return corrected if corrected else text, score, confidence

    def _method3_adaptive(
        self,
        gray,
        custom_config: str,
        context: OCRContext
    ) -> Tuple[str, int, float]:
        """Method 3: Adaptive thresholding."""
        import cv2

        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        self._save_method_debug_image(adaptive, context, "method3_adaptive")

        text, confidence = self._ocr_text_and_confidence(adaptive, custom_config)
        text = self.ocr_enhancer.apply_pattern_correction(text)
        score, corrected = self.validator.validate_and_score(text) if text else (-1, "")
        return corrected if corrected else text, score, confidence

    def _method4_otsu(
        self,
        gray,
        custom_config: str,
        context: OCRContext
    ) -> Tuple[str, int, float]:
        """Method 4: OTSU thresholding after denoise."""
        import cv2

        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        self._save_method_debug_image(thresh, context, "method4_otsu")

        text, confidence = self._ocr_text_and_confidence(thresh, custom_config)
        text = self.ocr_enhancer.apply_pattern_correction(text)
        score, corrected = self.validator.validate_and_score(text) if text else (-1, "")
        return corrected if corrected else text, score, confidence

    def _method5_bilateral(
        self,
        gray,
        custom_config: str,
        context: OCRContext
    ) -> Tuple[str, int, float]:
        """Method 5: Bilateral filter + OTSU threshold."""
        import cv2

        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        self._save_method_debug_image(thresh, context, "method5_bilateral")

        text, confidence = self._ocr_text_and_confidence(thresh, custom_config)
        text = self.ocr_enhancer.apply_pattern_correction(text)
        score, corrected = self.validator.validate_and_score(text) if text else (-1, "")
        return corrected if corrected else text, score, confidence

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

        if not self._tesseract_available:
            return []

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

        confidences = [
            float(r.get("confidence", 0.0))
            for r in method_results.values()
            if isinstance(r, dict) and "confidence" in r
        ]
        confidences = [c for c in confidences if c >= 0]
        if confidences:
            return sum(confidences) / len(confidences)

        # Backward-compatible fallback for old method results without confidence.
        scores = [r.get("score", 0) for r in method_results.values() if isinstance(r, dict)]
        if not scores:
            return 0.0
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
