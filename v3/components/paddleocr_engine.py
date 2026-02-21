"""
PaddleOCREngine - PaddleOCR wrapper สำหรับ CPU-only inference

ใช้ PaddleOCR เป็น fallback เมื่อ Tesseract ให้ผลลัพธ์ที่ไม่น่าเชื่อถือ
รองรับ CPU-only (ไม่ต้องการ GPU)
"""

import logging
from typing import Tuple, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


class PaddleOCREngine:
    """
    PaddleOCR Engine Wrapper สำหรับ CPU-only

    ใช้ Singleton pattern เพื่อประหยัด memory
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        lang: str = 'en'
    ):
        """
        Initialize PaddleOCR Engine

        Args:
            lang: Language code ('en', 'ch', etc.)
        """
        # Skip if already initialized (Singleton)
        if PaddleOCREngine._initialized:
            return

        logger.info("Initializing PaddleOCR (CPU mode)...")

        try:
            from paddleocr import PaddleOCR

            # PaddleOCR 3.x uses different parameters
            self.ocr = PaddleOCR(
                lang=lang,
                use_textline_orientation=True
            )

            self.lang = lang
            PaddleOCREngine._initialized = True

            logger.info(f"PaddleOCR initialized successfully (lang={lang})")

        except ImportError as e:
            logger.error(f"PaddleOCR not installed. Run: pip install paddlepaddle paddleocr")
            raise ImportError(
                "PaddleOCR not installed. Install with: "
                "pip install paddlepaddle paddleocr"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise

    def extract_text(
        self,
        image: np.ndarray,
        clean_result: bool = True,
        allowed_chars: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
    ) -> Tuple[str, float]:
        """
        Extract text from image

        Args:
            image: OpenCV image (BGR format)
            clean_result: Whether to clean the result (remove spaces, filter chars)
            allowed_chars: Characters to keep when cleaning

        Returns:
            Tuple of (text, confidence)
            - text: Extracted text
            - confidence: Average confidence (0-100)
        """
        try:
            result = self._run_ocr(image)

            if not result or not result[0]:
                logger.debug("PaddleOCR returned empty result")
                return "", 0.0

            # Extract text and confidence
            texts = []
            confidences = []

            for line in result[0]:
                if len(line) >= 2 and len(line[1]) >= 2:
                    text = str(line[1][0])
                    conf = float(line[1][1])
                    texts.append(text)
                    confidences.append(conf)

            if not texts:
                return "", 0.0

            # Join all text
            full_text = ''.join(texts)

            # Calculate average confidence
            avg_conf = sum(confidences) / len(confidences) * 100

            if clean_result:
                # Remove spaces and keep only allowed chars
                allowed_set = set(allowed_chars)
                full_text = ''.join(c for c in full_text if c in allowed_set)

            logger.debug(f"PaddleOCR result: '{full_text}' (confidence: {avg_conf:.1f}%)")

            return full_text, avg_conf

        except Exception as e:
            logger.error(f"PaddleOCR extraction error: {e}")
            return "", 0.0

    def extract_text_with_details(
        self,
        image: np.ndarray,
        clean_result: bool = True,
        allowed_chars: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
    ) -> dict:
        """
        Extract text from image with detailed information

        Args:
            image: OpenCV image (BGR format)
            clean_result: Whether to clean the result
            allowed_chars: Characters to keep when cleaning

        Returns:
            Dict with:
            - text: Extracted text
            - confidence: Average confidence
            - boxes: Bounding boxes
            - char_details: Per-character confidence
        """
        try:
            result = self._run_ocr(image)

            if not result or not result[0]:
                return {
                    'text': '',
                    'confidence': 0.0,
                    'boxes': [],
                    'char_details': []
                }

            texts = []
            confidences = []
            boxes = []
            char_details = []

            for line in result[0]:
                if len(line) >= 2:
                    box = line[0]  # Bounding box coordinates
                    text = str(line[1][0])
                    conf = float(line[1][1])

                    texts.append(text)
                    confidences.append(conf)
                    boxes.append(box)

                    # Add per-character details
                    for char in text:
                        char_details.append({
                            'char': char,
                            'confidence': conf * 100  # Approximate per-char confidence
                        })

            full_text = ''.join(texts)
            avg_conf = sum(confidences) / len(confidences) * 100 if confidences else 0.0

            if clean_result:
                allowed_set = set(allowed_chars)
                full_text = ''.join(c for c in full_text if c in allowed_set)

            return {
                'text': full_text,
                'confidence': avg_conf,
                'boxes': boxes,
                'char_details': char_details
            }

        except Exception as e:
            logger.error(f"PaddleOCR extraction error: {e}")
            return {
                'text': '',
                'confidence': 0.0,
                'boxes': [],
                'char_details': []
            }

    def _run_ocr(self, image: np.ndarray):
        """
        Run OCR with compatibility between PaddleOCR major versions.

        PaddleOCR 2.x accepts `cls=True` on `ocr()`, while newer
        versions can raise TypeError for this keyword.
        """
        try:
            return self.ocr.ocr(image, cls=True)
        except TypeError as e:
            if "unexpected keyword argument 'cls'" in str(e):
                logger.debug("PaddleOCR API does not accept `cls`; retrying without it")
                return self.ocr.ocr(image)
            raise

    def is_available(cls) -> bool:
        """Check if PaddleOCR is available"""
        try:
            import paddleocr
            return True
        except ImportError:
            return False


def get_paddleocr_engine(
    lang: str = 'en'
) -> Optional[PaddleOCREngine]:
    """
    Factory function to get PaddleOCR engine instance

    Args:
        lang: Language code

    Returns:
        PaddleOCREngine instance or None if not available
    """
    try:
        return PaddleOCREngine(lang=lang)
    except ImportError:
        logger.warning("PaddleOCR not available")
        return None
    except Exception as e:
        logger.error(f"Failed to create PaddleOCR engine: {e}")
        return None
