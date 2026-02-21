"""
HeaderValidator - validate, normalize, and compare extracted headers.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, Tuple

from v3.utils.config_manager import ExtractionConfig

logger = logging.getLogger(__name__)


class HeaderValidator:
    """
    Validate and score OCR header strings.

    Expected common format:
    - 4 parts: A-CC-CODE-S12345678
    - 3 parts: A-CODE-S12345678 (fallback format)
    """

    def __init__(self, config: ExtractionConfig):
        self.config = config
        self._ambiguous_map = self._parse_ambiguous_map(config.ambiguous_characters)
        self._header_pattern = re.compile(config.header_pattern) if config.header_pattern else None

    def validate_and_score(self, text: str) -> Tuple[int, str]:
        """
        Validate and score header text.

        Returns:
            (score, corrected_text)
        """
        corrected = self._normalize(text)
        if not corrected:
            return 0, ""

        score = 0

        # Basic quality checks
        score += 10
        if self._has_only_allowed_chars(corrected):
            score += 15

        parts = corrected.split(self.config.expected_separator)
        if len(parts) >= self.config.min_expected_parts:
            score += 20

        # Strong score path using configured regex
        if self.config.enable_pattern_check and self._header_pattern and self._header_pattern.match(corrected):
            score += 120
            return score, corrected

        # Structured fallback validation
        structure_score = self._score_structure(parts)
        score += structure_score

        return score, corrected

    def headers_match(self, header1: str, header2: str, threshold: float = 1.0) -> bool:
        """
        Compare two headers and decide if they represent the same logical header.
        """
        _, a = self.validate_and_score(header1)
        _, b = self.validate_and_score(header2)

        if not a or not b:
            return False
        if a == b:
            return True

        parts_a = a.split(self.config.expected_separator)
        parts_b = b.split(self.config.expected_separator)

        # Serial-based matching: keep grouping stable when serial OCR has tiny noise.
        if self.config.enable_serial_based_matching and len(parts_a) >= 3 and len(parts_b) >= 3:
            prefix_a = parts_a[:-1]
            prefix_b = parts_b[:-1]
            if prefix_a == prefix_b and self._serials_close(parts_a[-1], parts_b[-1]):
                return True

        similarity = SequenceMatcher(None, a, b).ratio()
        norm_threshold = threshold / 100.0 if threshold > 1.0 else threshold
        return similarity >= norm_threshold

    def _normalize(self, text: str) -> str:
        if not text:
            return ""

        s = str(text).strip().upper()
        s = re.sub(r"\s+", "", s)

        # Keep only configured whitelist and separator.
        allowed = set(self.config.character_whitelist + self.config.expected_separator)
        s = "".join(ch for ch in s if ch in allowed)

        # Collapse duplicated separators and trim ends.
        sep = re.escape(self.config.expected_separator)
        s = re.sub(f"{sep}+", self.config.expected_separator, s).strip(self.config.expected_separator)

        # Apply ambiguity normalization only to segments that should be mostly digits.
        parts = s.split(self.config.expected_separator)
        if len(parts) >= 1:
            parts[-1] = self._normalize_serial(parts[-1])

        return self.config.expected_separator.join(parts)

    def _normalize_serial(self, serial: str) -> str:
        if not serial:
            return serial

        # Keep first char as-is (often S/R prefix), normalize the rest with map.
        if len(serial) == 1:
            return serial

        prefix, rest = serial[0], serial[1:]
        normalized = "".join(self._ambiguous_map.get(ch, ch) for ch in rest)
        return prefix + normalized

    def _has_only_allowed_chars(self, text: str) -> bool:
        allowed = set(self.config.character_whitelist + self.config.expected_separator)
        return all(ch in allowed for ch in text)

    def _score_structure(self, parts) -> int:
        score = 0

        if len(parts) == self.config.expected_parts:
            score += 20
            prefix, country, code, serial = parts[0], parts[1], parts[2], parts[3]

            if len(prefix) == self.config.pattern_prefix_length and prefix.isalpha():
                score += 15
            if self.config.pattern_country_min <= len(country) <= self.config.pattern_country_max and country.isalpha():
                score += 15
            if self.config.pattern_code_min <= len(code) <= self.config.pattern_code_max and code.isalnum():
                score += 20
            if self._valid_serial(serial):
                score += 35
            return score

        if len(parts) == self.config.min_expected_parts:
            # Fallback 3-part format: prefix, code, serial
            score += 10
            prefix, code, serial = parts[0], parts[1], parts[2]

            if len(prefix) == self.config.pattern_prefix_length and prefix.isalpha():
                score += 10
            if self.config.pattern_code_min <= len(code) <= self.config.pattern_code_max and code.isalnum():
                score += 15
            if self._valid_serial(serial):
                score += 20
            return score

        return score

    def _valid_serial(self, serial: str) -> bool:
        if not serial:
            return False
        if serial[0] not in self.config.pattern_serial_allowed_prefixes:
            return False

        digits = "".join(ch for ch in serial[1:] if ch.isdigit())
        if len(digits) < self.config.min_digit_count:
            return False
        if len(digits) > self.config.expected_digit_count + 2:
            return False

        serial_len = len(serial)
        return self.config.pattern_serial_min <= serial_len <= self.config.pattern_serial_max

    def _serials_close(self, serial_a: str, serial_b: str) -> bool:
        if not serial_a or not serial_b:
            return False

        digits_a = "".join(ch for ch in serial_a if ch.isdigit())
        digits_b = "".join(ch for ch in serial_b if ch.isdigit())
        if not digits_a or not digits_b:
            return False

        ratio = SequenceMatcher(None, digits_a, digits_b).ratio()
        return ratio >= 0.85

    def _parse_ambiguous_map(self, mapping: str) -> Dict[str, str]:
        """
        Parse config map like: 'S:5,B:8,P:F,O:0,I:1,Z:2'
        """
        result: Dict[str, str] = {}
        if not mapping:
            return result

        for pair in mapping.split(","):
            token = pair.strip()
            if ":" not in token:
                continue
            src, dst = token.split(":", 1)
            src = src.strip().upper()
            dst = dst.strip().upper()
            if len(src) == 1 and len(dst) == 1:
                result[src] = dst
        return result
