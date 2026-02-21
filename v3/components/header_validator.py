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

        serial = parts[-1] if parts else ""
        serial_valid = self._valid_serial(serial)

        # Regex bonus, but do not early-return. We still gate final score by serial validity.
        if self.config.enable_pattern_check and self._header_pattern and self._header_pattern.match(corrected):
            score += 60

        # Structured fallback validation
        structure_score = self._score_structure(parts)
        score += structure_score

        # Hard gate: invalid serial cannot be high-confidence.
        if not serial_valid:
            score = min(score, self.config.invalid_serial_score_cap)

        return score, corrected

    def is_strict_header(self, text: str) -> bool:
        """Check if normalized header passes strict serial validation."""
        _, corrected = self.validate_and_score(text)
        if not corrected:
            return False
        parts = corrected.split(self.config.expected_separator)
        if len(parts) < self.config.min_expected_parts:
            return False
        return self._valid_serial(parts[-1])

    def headers_match(self, header1: str, header2: str, threshold: float = 1.0) -> bool:
        """
        Compare two headers and decide if they represent the same logical header.
        """
        score_a, a = self.validate_and_score(header1)
        score_b, b = self.validate_and_score(header2)

        if not a or not b:
            return False
        if a == b:
            return True

        parts_a = a.split(self.config.expected_separator)
        parts_b = b.split(self.config.expected_separator)

        # Serial-based matching: if both headers are high-confidence, require exact
        # serial match to avoid merging different documents with similar serials.
        if self.config.enable_serial_based_matching and len(parts_a) >= 3 and len(parts_b) >= 3:
            prefix_a = parts_a[:-1]
            prefix_b = parts_b[:-1]
            if prefix_a == prefix_b:
                serial_a = parts_a[-1]
                serial_b = parts_b[-1]
                strict_a = self._valid_serial(serial_a)
                strict_b = self._valid_serial(serial_b)

                # Both strict: must be exact serial match.
                if strict_a and strict_b:
                    return serial_a == serial_b

                # One strict + one weak: allow close match for OCR drift correction.
                if strict_a != strict_b and self._serials_close(serial_a, serial_b):
                    return True

                # Both weak/non-strict: be conservative and require exact equality
                # to prevent false merges like R4092558 vs R4092528.
                if not strict_a and not strict_b:
                    return serial_a == serial_b

                return False

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

        # Repair missing separator in first block only when pattern is strongly suspicious,
        # e.g. RLWK-RWC-S1R015003 -> R-LWK-RWC-S1R015003
        s = self._repair_first_block_separator(s)

        # Apply ambiguity normalization only to segments that should be mostly digits.
        parts = s.split(self.config.expected_separator)
        if len(parts) >= 1:
            parts[-1] = self._normalize_serial(parts[-1])

        return self.config.expected_separator.join(parts)

    def _repair_first_block_separator(self, text: str) -> str:
        """
        Repair headers where first separator is missing.

        Conservative rule:
        - exactly 3 parts
        - first part length >= 4
        - first char alphabetic (likely prefix)
        """
        parts = text.split(self.config.expected_separator)
        if len(parts) != 3:
            return text
        if len(parts[0]) < 4:
            return text
        if not parts[0][0].isalpha():
            return text
        if not parts[0].isalnum():
            return text

        prefix = parts[0][0]
        middle = parts[0][1:]
        repaired = self.config.expected_separator.join([prefix, middle, parts[1], parts[2]])
        logger.debug(f"Repaired missing separator: '{text}' -> '{repaired}'")
        return repaired

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
            # 4-part format: prefix / segment / segment / serial
            score += 20
            prefix, country, code, serial = parts[0], parts[1], parts[2], parts[3]

            if len(prefix) == self.config.pattern_prefix_length and prefix.isalpha():
                score += 15
            elif len(prefix) <= 2 and prefix.isalnum():
                score += 8

            # Keep middle segments flexible because some docs hide country/code semantics.
            if 1 <= len(country) <= 6 and country.isalnum():
                score += 12
            if 1 <= len(code) <= 6 and code.isalnum():
                score += 15

            if self._valid_serial(serial):
                score += 35
            elif self._has_serial_like_digits(serial):
                score += 4
            return score

        if len(parts) == self.config.min_expected_parts:
            # Flexible 3-part format: prefix / segment / serial
            score += 10
            prefix, middle, serial = parts[0], parts[1], parts[2]

            if len(prefix) == self.config.pattern_prefix_length and prefix.isalpha():
                score += 10
            elif len(prefix) <= 2 and prefix.isalnum():
                score += 6

            if 1 <= len(middle) <= 8 and middle.isalnum():
                score += 15

            if self._valid_serial(serial):
                score += 25
            elif self._has_serial_like_digits(serial):
                score += 4
            return score

        return score

    def _valid_serial(self, serial: str) -> bool:
        if not serial:
            return False
        serial = serial.upper()

        starts_with_allowed = serial[0] in self.config.pattern_serial_allowed_prefixes

        if self.config.serial_prefix_required and not starts_with_allowed:
            return False

        serial_body = serial[1:] if starts_with_allowed else serial
        if not serial_body:
            return False
        if not serial_body.isdigit():
            return False
        digits = serial_body

        if len(digits) < self.config.min_digit_count:
            return False
        if self.config.serial_digits_exact > 0:
            if len(digits) != self.config.serial_digits_exact:
                return False
        elif len(digits) > self.config.expected_digit_count + 2:
            return False

        digit_ratio = len(digits) / max(1, len(serial))
        if digit_ratio < 0.5:
            return False

        if starts_with_allowed:
            serial_len = len(serial)
            return self.config.pattern_serial_min <= serial_len <= self.config.pattern_serial_max

        # Allow masked/secure serial variants without strict prefix.
        return serial.isalnum() and len(serial) >= self.config.min_digit_count

    def _has_serial_like_digits(self, serial: str) -> bool:
        digits = "".join(ch for ch in serial if ch.isdigit())
        return len(digits) >= self.config.min_digit_count

    def _serials_close(self, serial_a: str, serial_b: str) -> bool:
        if not serial_a or not serial_b:
            return False

        digits_a = "".join(ch for ch in serial_a if ch.isdigit())
        digits_b = "".join(ch for ch in serial_b if ch.isdigit())
        if not digits_a or not digits_b:
            return False

        ratio = SequenceMatcher(None, digits_a, digits_b).ratio()
        return ratio >= self.config.serial_close_match_threshold

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
