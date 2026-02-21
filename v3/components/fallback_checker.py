"""
FallbackChecker - ตรวจสอบเงื่อนไขการเรียก PaddleOCR

เงื่อนไขที่จะเรียก PaddleOCR:
1. Regex ไม่ผ่าน - ผลลัพธ์ไม่ตรงกับ pattern
2. Confidence ต่ำ - Tesseract confidence < threshold
3. ตัวอักษรนอก whitelist - เจอตัวอักษรที่ไม่ใช่ A-Z, 0-9, หรือ -
4. Ambiguity สูง - เจอตัวอักษรที่สับสนง่าย (S/5, B/8, P/F, O/0, I/1, Z/2)
"""

import re
import logging
from typing import Tuple, List, Optional, Union

logger = logging.getLogger(__name__)


class FallbackChecker:
    """ตรวจสอบเงื่อนไขการเรียก PaddleOCR"""

    # คู่ตัวอักษรที่สับสนง่าย
    AMBIGUOUS_PAIRS = {
        'S': '5', '5': 'S',
        'B': '8', '8': 'B',
        'P': 'F', 'F': 'P',
        'O': '0', '0': 'O',
        'I': '1', '1': 'I',
        'Z': '2', '2': 'Z',
        'G': '6', '6': 'G',
        'D': '0', 'Q': 'O',
    }

    def __init__(
        self,
        config=None,
        confidence_threshold: float = 85.0,
        header_pattern: str = r'^[A-Z]-[A-Z]{1,2}-[A-Z0-9]{2,4}-[SR][0-9]{6,8}$',
        character_whitelist: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
        ambiguous_characters: str = 'S:5,B:8,P:F,O:0,I:1,Z:2',
        enable_pattern_check: bool = True
    ):
        """
        Initialize FallbackChecker

        Args:
            config: ExtractionConfig object (V3.2+) - ถ้าให้มาจะใช้ค่าจาก config
            confidence_threshold: Tesseract confidence threshold (0-100)
            header_pattern: Regex pattern for header validation
            character_whitelist: Allowed characters
            ambiguous_characters: Ambiguous character pairs (format: 'S:5,B:8')
            enable_pattern_check: Enable/disable pattern validation
        """
        # ถ้าให้ ExtractionConfig มา ให้ใช้ค่าจาก config
        if config is not None and hasattr(config, 'tesseract_confidence_threshold'):
            confidence_threshold = config.tesseract_confidence_threshold
            header_pattern = config.header_pattern
            character_whitelist = config.character_whitelist
            ambiguous_characters = config.ambiguous_characters
            enable_pattern_check = config.enable_pattern_check

        self.confidence_threshold = confidence_threshold
        self.pattern = re.compile(header_pattern)
        self.whitelist = set(character_whitelist)
        self.enable_pattern_check = enable_pattern_check
        self.ambiguous_chars = self._parse_ambiguous(ambiguous_characters)

        logger.info(f"FallbackChecker initialized with confidence_threshold={confidence_threshold}")

    def _parse_ambiguous(self, ambiguous_str: str) -> dict:
        """
        Parse ambiguous character pairs

        Args:
            ambiguous_str: String like 'S:5,B:8,P:F'

        Returns:
            Dict mapping each char to its ambiguous counterpart
        """
        pairs = {}
        if not ambiguous_str:
            return pairs

        for pair in ambiguous_str.split(','):
            if ':' in pair:
                k, v = pair.split(':')
                k = k.strip()
                v = v.strip()
                pairs[k] = v
                pairs[v] = k  # Bidirectional

        return pairs

    def should_fallback(
        self,
        text: str,
        confidence: float,
        tesseract_char_data: Optional[List[dict]] = None
    ) -> Tuple[bool, str]:
        """
        ตรวจสอบว่าควรเรียก PaddleOCR หรือไม่

        Args:
            text: OCR result text
            confidence: Tesseract confidence (0-100)
            tesseract_char_data: Optional per-character confidence data
                [{'char': 'B', 'confidence': 95}, ...]

        Returns:
            (should_fallback: bool, reason: str)
        """
        if not text:
            return True, "empty_text"

        reasons = []

        # 1. Regex ไม่ผ่าน
        if self.enable_pattern_check and not self.pattern.match(text):
            reasons.append("regex_failed")

        # 2. Confidence ต่ำ
        if confidence < self.confidence_threshold:
            reasons.append(f"low_confidence({confidence:.1f}%)")

        # 3. ตัวอักษรนอก whitelist
        invalid_chars = set(text) - self.whitelist
        if invalid_chars:
            reasons.append(f"invalid_chars({''.join(sorted(invalid_chars))})")

        # 4. Ambiguity สูง - ตรวจสอบตัวอักษรที่สับสนง่าย
        ambiguous_found = self._check_ambiguity(text, tesseract_char_data)
        if ambiguous_found:
            reasons.append(f"ambiguous({','.join(ambiguous_found)})")

        should = len(reasons) > 0
        reason_str = ", ".join(reasons) if reasons else "passed"

        if should:
            logger.debug(f"Fallback triggered for '{text}': {reason_str}")

        return should, reason_str

    def _check_ambiguity(
        self,
        text: str,
        tesseract_char_data: Optional[List[dict]] = None
    ) -> List[str]:
        """
        ตรวจสอบตัวอักษรที่สับสนง่าย

        Args:
            text: OCR result text
            tesseract_char_data: Per-character confidence data

        Returns:
            List of ambiguous characters found (e.g., ['S->5', 'B->8'])
        """
        ambiguous = []

        # ตรวจสอบจาก tesseract confidence data (ถ้ามี)
        if tesseract_char_data:
            for char_data in tesseract_char_data:
                char = char_data.get('char', '')
                conf = char_data.get('confidence', 100)

                # ถ้าตัวอักษรที่สับสนง่ายมี confidence ต่ำ
                if char in self.ambiguous_chars and conf < 90:
                    ambiguous.append(f"{char}->{self.ambiguous_chars[char]}")

        # ถ้าไม่มี char data, ตรวจสอบจากตัวอักษรที่สับสนง่ายในข้อความ
        if not ambiguous:
            for char in text:
                if char in self.ambiguous_chars:
                    # ตรวจสอบว่าอยู่ในตำแหน่งที่อาจสับสน
                    # (เช่น ตัวเลขในส่วนที่ควรเป็นตัวอักษร หรือกลับกัน)
                    pass  # สำหรับตอนนี้ ให้ skip

        return ambiguous

    def get_all_triggers(
        self,
        text: str,
        confidence: float,
        tesseract_char_data: Optional[List[dict]] = None
    ) -> dict:
        """
        ได้รับรายละเอียดของทุก trigger

        Returns:
            Dict with trigger details
        """
        result = {
            'text': text,
            'confidence': confidence,
            'triggers': {
                'regex_failed': False,
                'low_confidence': False,
                'invalid_chars': [],
                'ambiguous_chars': []
            },
            'should_fallback': False,
            'reason': ''
        }

        # 1. Regex check
        if self.enable_pattern_check:
            result['triggers']['regex_failed'] = not self.pattern.match(text)

        # 2. Confidence check
        result['triggers']['low_confidence'] = confidence < self.confidence_threshold

        # 3. Invalid chars
        invalid_chars = set(text) - self.whitelist
        result['triggers']['invalid_chars'] = list(invalid_chars)

        # 4. Ambiguity
        result['triggers']['ambiguous_chars'] = self._check_ambiguity(text, tesseract_char_data)

        # Overall result
        should, reason = self.should_fallback(text, confidence, tesseract_char_data)
        result['should_fallback'] = should
        result['reason'] = reason

        return result


def create_fallback_checker_from_config(config) -> FallbackChecker:
    """
    Factory function to create FallbackChecker from config

    Args:
        config: ExtractionConfig object (V3.2+) or legacy ConfigParser

    Returns:
        FallbackChecker instance
    """
    # V3.2+: ถ้าเป็น ExtractionConfig ให้ส่งเข้าไปใน constructor โดยตรง
    if hasattr(config, 'tesseract_confidence_threshold'):
        return FallbackChecker(config=config)

    # Legacy: ลองอ่านจาก ConfigParser
    try:
        section = config['Settings'] if 'Settings' in config else config
        return FallbackChecker(
            confidence_threshold=float(section.get('tesseract_confidence_threshold', 85.0)),
            header_pattern=section.get('header_pattern',
                                       r'^[A-Z]-[A-Z]{1,2}-[A-Z0-9]{2,4}-[SR][0-9]{6,8}$'),
            character_whitelist=section.get('character_whitelist',
                                            'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'),
            ambiguous_characters=section.get('ambiguous_characters', 'S:5,B:8,P:F,O:0,I:1,Z:2'),
            enable_pattern_check=section.get('enable_pattern_check', 'True').lower() == 'true'
        )
    except Exception as e:
        logger.warning(f"Error reading config, using defaults: {e}")
        return FallbackChecker()
