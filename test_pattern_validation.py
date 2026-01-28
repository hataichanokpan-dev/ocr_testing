"""
Test Pattern Validation System
Tests the new pattern-based validation with various inputs
"""

import configparser
from pdf_extractorV2 import PDFTextExtractor

# Create test config
config = configparser.ConfigParser()
config['Settings'] = {
    'header_area_top': '2',
    'header_area_left': '12',
    'header_area_width': '42',
    'header_area_height': '4',
    'pages_to_read': '1',
    'expected_parts': '4',
    'expected_separator': '-',
    'expected_digit_count': '8',
    'min_digit_count': '6',
    'enable_pattern_validation': 'True',
    'pattern_prefix_length': '1',
    'pattern_country_min': '1',
    'pattern_country_max': '2',
    'pattern_code_min': '2',
    'pattern_code_max': '4',
    'pattern_serial_min': '7',
    'pattern_serial_max': '9',
    'pattern_serial_allowed_prefixes': 'S,R',
    'enable_api_logging': 'False'
}

extractor = PDFTextExtractor(config)

# Test cases
test_cases = [
    # Valid cases (should get high scores)
    ("B-C-5U5-R4091534", "VALID: Perfect R-prefix format (9 chars)"),
    ("B-C-5U5-S1789384", "VALID: Perfect S-prefix format (8 chars)"),
    ("A-US-GTX-R123456", "VALID: Minimum length (7 chars)"),
    ("B-F-AB12-S12345678", "VALID: Maximum length (9 chars)"),
    
    # Invalid prefix letter
    ("B-C-5U5-T4091534", "INVALID: T-prefix (not S or R)"),
    ("B-C-5U5-A1234567", "INVALID: A-prefix (not S or R)"),
    ("B-C-5U5-X9876543", "INVALID: X-prefix (not S or R)"),
    
    # Invalid format (has non-digits after prefix)
    ("B-C-5U5-R409153A", "INVALID: Has letter 'A' after digits"),
    ("B-C-5U5-S12AB567", "INVALID: Has 'AB' in middle"),
    ("B-C-5U5-R4091A34", "INVALID: Has letter in middle"),
    
    # Invalid length
    ("B-C-5U5-R40915", "INVALID: Too short (6 chars)"),
    ("B-C-5U5-S123456789", "INVALID: Too long (10 chars)"),
    
    # With noise (should get penalty)
    ("B-C-5U5-R4091534 9", "VALID with trailing noise '9'"),
    ("B-C-5U5-S1789384 G", "VALID with trailing noise 'G'"),
    
    # Edge cases
    ("B-C-5U5-r4091534", "VALID: Lowercase prefix (should auto-convert)"),
    ("B-C-5U5-s1234567", "VALID: Lowercase s-prefix"),
]

print("=" * 80)
print("PATTERN VALIDATION TEST RESULTS")
print("=" * 80)
print()

for text, description in test_cases:
    print(f"Test: {description}")
    print(f"Input: '{text}'")
    score = extractor._validate_with_pattern(text)
    print(f"Score: {score}")
    print("-" * 80)
    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
