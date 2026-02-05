"""
Header Validator - Pattern validation and scoring
Extracted from V2 with improvements
"""

import re
import logging
from typing import Tuple
from v3.utils.config_manager import ExtractionConfig

logger = logging.getLogger(__name__)


class HeaderValidator:
    """
    Validates and scores extracted header text
    
    Supports both 4-part and 3-part formats:
    - 4-part: [Prefix]-[Country]-[Code]-[Serial] (e.g., B-HK-WFE-S17975643)
    - 3-part: [Prefix]-[Code]-[Serial] (e.g., B-WFE-S17975643)
    """
    
    def __init__(self, config: ExtractionConfig):
        """
        Initialize validator with configuration
        
        Args:
            config: Extraction configuration
        """
        self.config = config
    
    def validate_and_score(self, text: str) -> Tuple[int, str]:
        """
        Validate and score OCR result
        
        Args:
            text: OCR extracted text
        
        Returns:
            Tuple[int, str]: (score, corrected_text)
                score: -1 if invalid, 0-100 if valid (higher is better)
                corrected_text: Text after structural corrections
        """
        if not text or len(text) < 10:
            return -1, text
        
        # Apply structural corrections
        corrected_text = self.apply_corrections(text)
        
        # Use pattern validation if enabled
        if self.config.enable_pattern_validation:
            score = self._validate_with_pattern(corrected_text)
        else:
            score = self._validate_legacy(corrected_text)
        
        return score, corrected_text
    
    def apply_corrections(self, text: str) -> str:
        """
        Apply minimal STRUCTURAL corrections only
        NO character-level fixes - let voting handle accuracy
        
        Only fixes:
        - Trailing/leading dashes (artifacts)
        - Double-prefix like BL-, RB- (structural error)
        - Serial prefix 8->S (very common structural error)
        """
        if not text:
            return text
        
        # Remove trailing dash/noise
        text = text.rstrip('-').rstrip()
        
        # Remove leading dash if followed by valid pattern
        if text.startswith('-'):
            potential = text.lstrip('-')
            parts = potential.split(self.config.expected_separator)
            if len(parts) >= 3 and len(parts[0]) <= 2 and parts[0].isalpha():
                text = potential
        
        # Fix obvious double-prefix
        parts = text.split(self.config.expected_separator)
        if len(parts) >= 3:
            prefix = parts[0].upper()
            double_prefix_fixes = {
                'BL': 'B', 'RB': 'B', 'PL': 'P',
            }
            if prefix in double_prefix_fixes:
                parts[0] = double_prefix_fixes[prefix]
                text = self.config.expected_separator.join(parts)
        
        # Fix serial prefix: 8xxxxxxxx -> Sxxxxxxxx
        parts = text.split(self.config.expected_separator)
        if len(parts) >= 3:
            serial = parts[-1]
            if len(serial) >= 8 and serial[0] == '8' and serial[1:].isdigit():
                parts[-1] = 'S' + serial[1:]
                text = self.config.expected_separator.join(parts)
        
        return text
    
    def _validate_with_pattern(self, text: str) -> int:
        """Validate text using detailed pattern rules"""
        score = 0
        parts = text.split(self.config.expected_separator)
        num_parts = len(parts)
        
        # Support both 3-part and 4-part formats
        if num_parts < self.config.min_expected_parts or num_parts > self.config.expected_parts:
            logger.debug(f"Invalid part count: {num_parts} (expected {self.config.min_expected_parts}-{self.config.expected_parts})")
            return -1
        
        if num_parts == 4:
            # Full 4-part format
            score += 60
            
            # Validate Part 1: Prefix
            if len(parts[0]) == self.config.pattern_prefix_length and parts[0].isalpha():
                score += 10
            else:
                score -= 20
            
            # Validate Part 2: Country
            country = parts[1]
            if self.config.pattern_country_min <= len(country) <= self.config.pattern_country_max and country.isalpha():
                score += 10
            else:
                score -= 20
            
            # Validate Part 3: Code
            code = parts[2]
            if self.config.pattern_code_min <= len(code) <= self.config.pattern_code_max and code.isalnum():
                score += 10
            else:
                score -= 20
            
            serial = parts[3].strip()
        
        elif num_parts == 3:
            # 3-part format
            score += 40
            
            # Validate Part 1: Prefix
            if len(parts[0]) <= 2 and parts[0].isalpha():
                score += 10
            else:
                score -= 20
            
            # Validate Part 2: Code
            code = parts[1]
            if 2 <= len(code) <= 5 and code.isalnum():
                score += 10
            else:
                score -= 20
            
            serial = parts[2].strip()
        else:
            return -1
        
        # Validate Serial (common for both formats)
        serial_clean = ''.join(c for c in serial if c.isalnum())
        
        # Smart extraction if too long
        if len(serial_clean) > self.config.pattern_serial_max and self.config.pattern_serial_allowed_prefixes:
            prefix_pattern = '|'.join(self.config.pattern_serial_allowed_prefixes)
            match = re.match(f'^([{prefix_pattern}])(\d+)', serial_clean, re.IGNORECASE)
            if match:
                serial_clean = match.group(1) + match.group(2)[:self.config.pattern_serial_max - 1]
        
        if self.config.pattern_serial_min <= len(serial_clean) <= self.config.pattern_serial_max:
            score += 40
            
            # Strict validation if allowed prefixes specified
            if self.config.pattern_serial_allowed_prefixes:
                first_char = serial_clean[0].upper()
                if first_char in self.config.pattern_serial_allowed_prefixes:
                    if serial_clean[1:].isdigit():
                        score += 20
                    else:
                        score -= 10
                else:
                    score -= 30
            else:
                if serial_clean[0].isalpha() and serial_clean[1:].isdigit():
                    score += 20
        else:
            score -= 30
        
        # Penalize trailing noise
        if serial != serial_clean:
            score -= 5
        
        score = max(score, -1)
        logger.debug(f"Pattern validation score: {score} for '{text}'")
        return score
    
    def _validate_legacy(self, text: str) -> int:
        """Legacy validation (fallback)"""
        score = 0
        parts = text.split(self.config.expected_separator)
        
        if len(parts) == self.config.expected_parts:
            score += 50
            
            last_part = parts[-1]
            if len(last_part) >= 8:
                score += 30
        
        total_digits = sum(c.isdigit() for c in text)
        if total_digits >= self.config.expected_digit_count:
            score += 20
        
        return score
    
    def extract_serial_number(self, header: str) -> str:
        """Extract serial number (last part) from header"""
        if not header:
            return None
        
        parts = header.split(self.config.expected_separator)
        if len(parts) >= self.config.min_expected_parts:
            serial = parts[-1].strip()
            serial_clean = ''.join(c for c in serial if c.isalnum())
            return serial_clean
        
        return None
    
    def normalize_header(self, header: str) -> str:
        """Normalize header for comparison (remove spaces, uppercase)"""
        if not header:
            return header
        return header.upper().replace(' ', '')
    
    def headers_match(self, header1: str, header2: str, threshold: float = 1.0) -> bool:
        """
        Check if two headers match
        
        Uses serial-based matching if enabled, otherwise similarity
        """
        if not header1 or not header2:
            return header1 == header2
        
        if header1 == header2:
            return True
        
        # Normalized match
        h1_norm = self.normalize_header(header1)
        h2_norm = self.normalize_header(header2)
        
        if h1_norm == h2_norm:
            return True
        
        # Serial-based matching
        if self.config.enable_serial_based_matching:
            serial1 = self.extract_serial_number(header1)
            serial2 = self.extract_serial_number(header2)
            
            if serial1 and serial2:
                return serial1 == serial2
        
        # Fallback to similarity
        if threshold >= 1.0:
            return False
        
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, h1_norm, h2_norm).ratio()
        return ratio >= threshold
