"""
Lightweight character classifier for OCR refinement.

Current use-case:
- Resolve ambiguous single glyph between 'O' and '0' in customer code segment.

Design goals:
- CPU friendly
- No external ML dependency (uses OpenCV HOG + linear SVM)
- Deterministic training from synthetic glyphs at startup
"""

import logging
import math
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ZeroOCharClassifier:
    """
    Two-class glyph classifier: {'0', 'O'}.

    It trains once from synthetic glyphs generated with OpenCV fonts.
    Runtime inference is a single HOG + linear SVM prediction per glyph.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_confidence: float = 0.72,
        min_margin: float = 0.12,
    ):
        self.enabled = bool(enabled)
        self.min_confidence = float(min_confidence)
        self.min_margin = float(min_margin)
        self._ready = False
        self._hog = None
        self._svm = None
        self._cv2 = None
        self._np = None

        if self.enabled:
            self._initialize()

    def is_ready(self) -> bool:
        return bool(self.enabled and self._ready and self._hog is not None and self._svm is not None)

    def predict(self, glyph_img) -> Optional[Dict[str, float]]:
        """
        Predict glyph class for a single character image.

        Returns:
            dict with keys:
            - predicted_char: '0' or 'O'
            - confidence: [0, 1]
            - margin: absolute linear distance from SVM boundary
            - accepted: bool (passes configured confidence/margin gates)
        """
        if not self.is_ready() or glyph_img is None:
            return None

        patch = self._normalize_glyph(glyph_img)
        if patch is None:
            return None

        features = self._hog.compute(patch)
        if features is None:
            return None
        features = features.reshape(1, -1).astype(self._np.float32)

        _ret, pred = self._svm.predict(features)
        predicted_idx = int(pred[0][0]) if pred is not None else 0
        predicted_char = "O" if predicted_idx == 1 else "0"

        margin = 0.0
        try:
            _ret2, _pred2, raw = self._svm.predict(features, flags=self._cv2.ml.STAT_MODEL_RAW_OUTPUT)
            margin = abs(float(raw[0][0]))
        except Exception:
            margin = 0.0

        confidence = 1.0 / (1.0 + math.exp(-margin))
        accepted = (confidence >= self.min_confidence) and (margin >= self.min_margin)

        return {
            "predicted_char": predicted_char,
            "confidence": float(confidence),
            "margin": float(margin),
            "accepted": bool(accepted),
        }

    def _initialize(self) -> None:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception as exc:
            logger.warning(f"ZeroOCharClassifier disabled: OpenCV/Numpy unavailable ({exc})")
            self._ready = False
            return

        self._cv2 = cv2
        self._np = np
        self._hog = cv2.HOGDescriptor(
            (24, 24),
            (12, 12),
            (6, 6),
            (6, 6),
            9,
        )

        train_x, train_y = self._build_training_set()
        if train_x is None or train_y is None or len(train_x) < 20:
            logger.warning("ZeroOCharClassifier disabled: insufficient synthetic training samples")
            self._ready = False
            return

        svm = cv2.ml.SVM_create()
        svm.setType(cv2.ml.SVM_C_SVC)
        svm.setKernel(cv2.ml.SVM_LINEAR)
        svm.setC(0.6)
        svm.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER, 500, 1e-6))
        svm.train(train_x, cv2.ml.ROW_SAMPLE, train_y)

        self._svm = svm
        self._ready = True
        logger.info("ZeroOCharClassifier initialized (HOG + Linear SVM)")

    def _build_training_set(self) -> Tuple[Optional[object], Optional[object]]:
        cv2 = self._cv2
        np = self._np
        if cv2 is None or np is None:
            return None, None

        fonts = [
            cv2.FONT_HERSHEY_SIMPLEX,
            cv2.FONT_HERSHEY_DUPLEX,
            cv2.FONT_HERSHEY_COMPLEX,
            cv2.FONT_HERSHEY_TRIPLEX,
            cv2.FONT_HERSHEY_COMPLEX_SMALL,
            cv2.FONT_HERSHEY_PLAIN,
        ]
        scales = [0.8, 1.0, 1.2, 1.4]
        thicknesses = [1, 2, 3]
        offsets = [-1, 0, 1]

        feats = []
        labels = []
        for glyph, label in (("0", 0), ("O", 1)):
            for font in fonts:
                for scale in scales:
                    for thickness in thicknesses:
                        for dx in offsets:
                            for dy in offsets:
                                canvas = np.full((56, 56), 255, dtype=np.uint8)
                                (tw, th), _base = cv2.getTextSize(glyph, font, scale, thickness)
                                x = max(0, (56 - tw) // 2 + dx)
                                y = min(55, max(th + 1, (56 + th) // 2 + dy))
                                cv2.putText(
                                    canvas,
                                    glyph,
                                    (x, y),
                                    font,
                                    scale,
                                    0,
                                    thickness,
                                    cv2.LINE_AA,
                                )

                                variants = [canvas]
                                variants.append(cv2.GaussianBlur(canvas, (3, 3), 0))
                                kernel = np.ones((2, 2), np.uint8)
                                variants.append(cv2.dilate(canvas, kernel, iterations=1))

                                for variant in variants:
                                    norm = self._normalize_glyph(variant)
                                    if norm is None:
                                        continue
                                    feature = self._hog.compute(norm)
                                    if feature is None:
                                        continue
                                    feats.append(feature.reshape(-1))
                                    labels.append(label)

        if not feats:
            return None, None

        x = np.array(feats, dtype=np.float32)
        y = np.array(labels, dtype=np.int32)
        return x, y

    def _normalize_glyph(self, glyph_img):
        cv2 = self._cv2
        np = self._np
        if cv2 is None or np is None:
            return None

        img = glyph_img
        if img is None:
            return None
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if img.size == 0:
            return None

        img = img.astype(np.uint8)
        _thr, bin_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(bin_img) < 127:
            bin_img = cv2.bitwise_not(bin_img)

        ys, xs = np.where(bin_img < 245)
        if len(xs) == 0 or len(ys) == 0:
            return None

        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        crop = bin_img[y1:y2 + 1, x1:x2 + 1]
        if crop.size == 0:
            return None

        h, w = crop.shape[:2]
        side = max(h, w) + 8
        square = np.full((side, side), 255, dtype=np.uint8)
        y0 = (side - h) // 2
        x0 = (side - w) // 2
        square[y0:y0 + h, x0:x0 + w] = crop

        resized = cv2.resize(square, (24, 24), interpolation=cv2.INTER_AREA)
        _thr2, resized = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return resized
