"""
Config Manager - Type-safe configuration management
Replaces raw ConfigParser with validated dataclasses
"""

from dataclasses import dataclass, field
from typing import List
import configparser
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """
    Type-safe configuration for PDF extraction
    
    All settings validated at initialization to catch config errors early
    """
    
    # Header region settings
    header_area_top: float = 0.0
    header_area_left: float = 0.0
    header_area_width: float = 100.0
    header_area_height: float = 15.0
    
    # Pages to process
    pages_to_read: List[int] = field(default_factory=lambda: [1])
    
    # Pattern validation
    enable_pattern_validation: bool = True
    expected_parts: int = 4
    min_expected_parts: int = 3
    expected_separator: str = '-'
    expected_digit_count: int = 8
    min_digit_count: int = 6
    
    # Pattern structure
    pattern_prefix_length: int = 1
    pattern_country_min: int = 1
    pattern_country_max: int = 2
    pattern_code_min: int = 2
    pattern_code_max: int = 4
    pattern_serial_min: int = 7
    pattern_serial_max: int = 10
    pattern_serial_allowed_prefixes: List[str] = field(default_factory=lambda: ['S', 'R'])
    serial_prefix_required: bool = True
    serial_digits_exact: int = 8
    invalid_serial_score_cap: int = 89
    serial_close_match_threshold: float = 0.85
    
    # Performance settings
    enable_parallel_processing: bool = True
    max_workers: int = 4
    
    # Adaptive rendering (NEW in V3)
    adaptive_rendering: bool = True
    initial_render_scale: float = 2.0
    max_render_scale: float = 6.0
    score_threshold_for_escalation: int = 70
    
    # OCR budget control (NEW in V3)
    max_ocr_attempts: int = 8
    early_exit_score: int = 90
    voting_method_score_threshold: int = 70
    ocr_method_early_exit_min_attempts: int = 2
    ocr_method_early_exit_min_confirmations: int = 2
    
    # OCR optimization
    ocr_filter_black_text: bool = True
    ocr_black_threshold: int = 100
    
    # OCR Enhancement (V3.1 - Full Upgrade)
    tesseract_cmd: str = ''
    tesseract_psm_mode: int = 7
    tesseract_char_whitelist: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
    enable_deskewing: bool = True
    enable_morphological_ops: bool = True
    enable_clahe: bool = True
    enable_multi_engine: bool = False
    use_easyocr: bool = False
    use_paddleocr: bool = False
    enable_pattern_correction: bool = True
    
    # Input/Output paths (NEW in V3)
    input_folder: str = 'input'
    output_base_dir: str = 'output'
    organize_by_year_and_date: bool = True
    output_retention_days: int = 90
    
    # Reports paths (V3.1)
    reports_base_dir: str = 'reports'
    reports_organize_by_date: bool = True
    
    # Debug images
    save_debug_images: bool = True
    debug_images_folder: str = 'debug_images'
    organize_by_date: bool = True
    save_method_images: bool = True
    image_retention_days: int = 30
    
    # API logging
    api_log_url: str = 'http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog'
    enable_api_logging: bool = True
    api_log_async: bool = True  # NEW in V3
    api_queue_size: int = 1000
    api_timeout: int = 5
    circuit_breaker_threshold: int = 5
    
    # Filename sanitization
    remove_special_chars: bool = True
    replace_spaces_with: str = '_'
    max_filename_length: int = 100
    
    # PDF splitting
    enable_pdf_splitting: bool = True
    min_pages_per_split: int = 1
    header_similarity_threshold: float = 1.0
    enable_serial_based_matching: bool = True
    split_naming_pattern: str = '{header}_pages_{start}-{end}'
    
    # Logging (NEW in V3)
    log_level: str = 'INFO'
    log_method_details: bool = False
    
    # Metrics tracking (NEW in V3)
    enable_metrics_tracking: bool = True
    metrics_export_path: str = 'metrics.json'

    # PaddleOCR Fallback Configuration (V3.2)
    enable_paddleocr_fallback: bool = True
    tesseract_confidence_threshold: float = 85.0
    enable_pattern_check: bool = True
    header_pattern: str = r'^[A-Z](?:-[A-Z0-9]{1,8}){1,2}-[SR][0-9]{7,8}$'
    ambiguous_characters: str = 'S:5,B:8,P:F,O:0,I:1,Z:2'
    character_whitelist: str = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
    enable_ensemble_voting: bool = True

    # Code ambiguity monitoring (observe-only, V3.3)
    enable_code_ambiguity_monitor: bool = True
    code_ambiguity_pairs: str = 'O:0,I:L'
    code_ambiguity_only_mixed_alnum: bool = True
    code_ambiguity_allow_same_type_pairs: bool = True
    enable_code_ambiguity_autocorrect: bool = False
    code_autocorrect_min_support: int = 1
    code_autocorrect_require_scale_evidence: bool = True
    code_autocorrect_force_multi_scale: bool = True
    enable_code_anchor_harmonize: bool = True
    code_anchor_harmonize_min_glyph_support: int = 1
    enable_code_glyph_disambiguation: bool = True
    code_zero_to_o_width_ratio: float = 1.12
    enable_code_char_classifier: bool = True
    code_char_classifier_min_confidence: float = 0.72
    code_char_classifier_min_margin: float = 0.12
    code_char_classifier_allow_leading_zero_to_o: bool = False
    code_char_classifier_enable_width_vote: bool = True
    code_char_classifier_min_vote_support: int = 2
    code_char_classifier_max_positions: int = 4
    code_char_classifier_require_evidence: bool = False
    code_char_classifier_min_evidence_support: int = 2
    code_char_tesseract_confidence_threshold: float = 72.0
    code_char_box_padding_ratio: float = 0.18
    enable_code_glyph_width_fallback: bool = False
    enable_code_ambiguity_confirm_high_scale: bool = True
    code_ambiguity_confirm_scale: float = 6.0
    enable_code_ambiguity_full_ocr_confirm: bool = True
    code_ambiguity_full_ocr_confirm_min_support: int = 2
    enable_code_image_support_rescue: bool = True
    code_image_support_min_votes: int = 1
    code_image_support_max_attempts: int = 6
    code_box_alignment_ambiguity_pairs: str = 'O:0,S:5,F:E,I:L'
    code_box_alignment_min_match_ratio: float = 0.35
    enable_code_anchor_rescue_pass: bool = True
    code_anchor_rescue_scale: float = 7.5
    code_anchor_rescue_only_on_no_char_boxes: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate header area
        if not (0 <= self.header_area_top <= 100):
            raise ValueError(f"header_area_top must be 0-100, got {self.header_area_top}")
        
        if not (0 <= self.header_area_width <= 100):
            raise ValueError(f"header_area_width must be 0-100, got {self.header_area_width}")
        
        # Validate render scales
        if self.initial_render_scale > self.max_render_scale:
            raise ValueError("initial_render_scale cannot exceed max_render_scale")
        
        # Validate workers
        if self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {self.max_workers}")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {self.log_level}")
        
        logger.info("Configuration validated successfully")


class ConfigManager:
    """
    Manages configuration loading and provides type-safe access
    """
    
    @staticmethod
    def load_from_file(config_path: str) -> ExtractionConfig:
        """
        Load configuration from INI file
        
        Args:
            config_path: Path to config.ini file
        
        Returns:
            ExtractionConfig: Validated configuration object
        """
        parser = configparser.ConfigParser()
        parser.read(config_path, encoding='utf-8')
        
        settings = parser['Settings'] if 'Settings' in parser else {}
        
        # Parse pages to read
        pages_str = settings.get('pages_to_read', '1').strip().lower()
        if pages_str == 'all':
            pages_to_read = []  # Empty list means 'all pages'
        else:
            pages_to_read = [int(p.strip()) for p in pages_str.split(',') if p.strip().isdigit()]
        
        # Parse serial prefixes
        prefixes_str = settings.get('pattern_serial_allowed_prefixes', 'S,R')
        allowed_prefixes = [p.strip().upper() for p in prefixes_str.split(',') if p.strip()]
        
        config = ExtractionConfig(
            # Header region
            header_area_top=settings.getfloat('header_area_top', 0.0),
            header_area_left=settings.getfloat('header_area_left', 0.0),
            header_area_width=settings.getfloat('header_area_width', 100.0),
            header_area_height=settings.getfloat('header_area_height', 15.0),
            
            # Pages
            pages_to_read=pages_to_read,
            
            # Pattern validation
            enable_pattern_validation=settings.getboolean('enable_pattern_validation', True),
            expected_parts=settings.getint('expected_parts', 4),
            min_expected_parts=settings.getint('min_expected_parts', 3),
            expected_separator=settings.get('expected_separator', '-'),
            expected_digit_count=settings.getint('expected_digit_count', 8),
            min_digit_count=settings.getint('min_digit_count', 6),
            
            # Pattern structure
            pattern_prefix_length=settings.getint('pattern_prefix_length', 1),
            pattern_country_min=settings.getint('pattern_country_min', 1),
            pattern_country_max=settings.getint('pattern_country_max', 2),
            pattern_code_min=settings.getint('pattern_code_min', 2),
            pattern_code_max=settings.getint('pattern_code_max', 4),
            pattern_serial_min=settings.getint('pattern_serial_min', 7),
            pattern_serial_max=settings.getint('pattern_serial_max', 10),
            pattern_serial_allowed_prefixes=allowed_prefixes,
            serial_prefix_required=settings.getboolean('serial_prefix_required', True),
            serial_digits_exact=settings.getint('serial_digits_exact', 8),
            invalid_serial_score_cap=settings.getint('invalid_serial_score_cap', 89),
            serial_close_match_threshold=settings.getfloat('serial_close_match_threshold', 0.85),
            
            # Performance
            enable_parallel_processing=settings.getboolean('enable_parallel_processing', True),
            max_workers=settings.getint('max_workers', 4),
            
            # Adaptive rendering
            adaptive_rendering=settings.getboolean('adaptive_rendering', True),
            initial_render_scale=settings.getfloat('initial_render_scale', 2.0),
            max_render_scale=settings.getfloat('max_render_scale', 6.0),
            score_threshold_for_escalation=settings.getint('score_threshold_for_escalation', 70),
            
            # OCR budget
            max_ocr_attempts=settings.getint('max_ocr_attempts', 8),
            early_exit_score=settings.getint('early_exit_score', 90),
            voting_method_score_threshold=settings.getint('voting_method_score_threshold', 70),
            ocr_method_early_exit_min_attempts=settings.getint('ocr_method_early_exit_min_attempts', 2),
            ocr_method_early_exit_min_confirmations=settings.getint('ocr_method_early_exit_min_confirmations', 2),
            
            # OCR optimization
            ocr_filter_black_text=settings.getboolean('ocr_filter_black_text', True),
            ocr_black_threshold=settings.getint('ocr_black_threshold', 100),
            
            # OCR Enhancement (V3.1)
            tesseract_cmd=settings.get('tesseract_cmd', ''),
            tesseract_psm_mode=settings.getint('tesseract_psm_mode', 7),
            tesseract_char_whitelist=settings.get('tesseract_char_whitelist', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'),
            enable_deskewing=settings.getboolean('enable_deskewing', True),
            enable_morphological_ops=settings.getboolean('enable_morphological_ops', True),
            enable_clahe=settings.getboolean('enable_clahe', True),
            enable_multi_engine=settings.getboolean('enable_multi_engine', False),
            use_easyocr=settings.getboolean('use_easyocr', False),
            use_paddleocr=settings.getboolean('use_paddleocr', False),
            enable_pattern_correction=settings.getboolean('enable_pattern_correction', True),
            
            # Input/Output paths
            input_folder=settings.get('input_folder', 'input'),
            output_base_dir=settings.get('output_base_dir', 'output'),
            organize_by_year_and_date=settings.getboolean('organize_by_year_and_date', True),
            output_retention_days=settings.getint('output_retention_days', 90),
            
            # Reports paths (V3.1)
            reports_base_dir=settings.get('reports_base_dir', 'reports'),
            reports_organize_by_date=settings.getboolean('reports_organize_by_date', True),
            
            # Debug images
            save_debug_images=settings.getboolean('save_debug_images', True),
            debug_images_folder=settings.get('debug_images_folder', 'debug_images'),
            organize_by_date=settings.getboolean('organize_by_date', True),
            save_method_images=settings.getboolean('save_method_images', True),
            image_retention_days=settings.getint('image_retention_days', 30),
            
            # API logging
            api_log_url=settings.get('api_log_url', 'http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog'),
            enable_api_logging=settings.getboolean('enable_api_logging', True),
            api_log_async=settings.getboolean('api_log_async', True),
            api_queue_size=settings.getint('api_queue_size', 1000),
            api_timeout=settings.getint('api_timeout', 5),
            circuit_breaker_threshold=settings.getint('circuit_breaker_threshold', 5),
            
            # Filename sanitization
            remove_special_chars=settings.getboolean('remove_special_chars', True),
            replace_spaces_with=settings.get('replace_spaces_with', '_'),
            max_filename_length=settings.getint('max_filename_length', 100),
            
            # PDF splitting
            enable_pdf_splitting=settings.getboolean('enable_pdf_splitting', True),
            min_pages_per_split=settings.getint('min_pages_per_split', 1),
            header_similarity_threshold=settings.getfloat('header_similarity_threshold', 1.0),
            enable_serial_based_matching=settings.getboolean('enable_serial_based_matching', True),
            split_naming_pattern=settings.get('split_naming_pattern', '{header}_pages_{start}-{end}'),
            
            # Logging
            log_level=settings.get('log_level', 'INFO'),
            log_method_details=settings.getboolean('log_method_details', False),
            
            # Metrics
            enable_metrics_tracking=settings.getboolean('enable_metrics_tracking', True),
            metrics_export_path=settings.get('metrics_export_path', 'metrics.json'),

            # PaddleOCR Fallback (V3.2)
            enable_paddleocr_fallback=settings.getboolean('enable_paddleocr_fallback', True),
            tesseract_confidence_threshold=settings.getfloat('tesseract_confidence_threshold', 85.0),
            enable_pattern_check=settings.getboolean('enable_pattern_check', True),
            header_pattern=settings.get('header_pattern', r'^[A-Z](?:-[A-Z0-9]{1,8}){1,2}-[SR][0-9]{7,8}$'),
            ambiguous_characters=settings.get('ambiguous_characters', 'S:5,B:8,P:F,O:0,I:1,Z:2'),
            character_whitelist=settings.get('character_whitelist', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'),
            enable_ensemble_voting=settings.getboolean('enable_ensemble_voting', True),

            # Code ambiguity monitoring (observe-only)
            enable_code_ambiguity_monitor=settings.getboolean('enable_code_ambiguity_monitor', True),
            code_ambiguity_pairs=settings.get('code_ambiguity_pairs', 'O:0,I:L'),
            code_ambiguity_only_mixed_alnum=settings.getboolean('code_ambiguity_only_mixed_alnum', True),
            code_ambiguity_allow_same_type_pairs=settings.getboolean('code_ambiguity_allow_same_type_pairs', True),
            enable_code_ambiguity_autocorrect=settings.getboolean('enable_code_ambiguity_autocorrect', False),
            code_autocorrect_min_support=settings.getint('code_autocorrect_min_support', 1),
            code_autocorrect_require_scale_evidence=settings.getboolean('code_autocorrect_require_scale_evidence', True),
            code_autocorrect_force_multi_scale=settings.getboolean('code_autocorrect_force_multi_scale', True),
            enable_code_anchor_harmonize=settings.getboolean('enable_code_anchor_harmonize', True),
            code_anchor_harmonize_min_glyph_support=settings.getint('code_anchor_harmonize_min_glyph_support', 1),
            enable_code_glyph_disambiguation=settings.getboolean('enable_code_glyph_disambiguation', True),
            code_zero_to_o_width_ratio=settings.getfloat('code_zero_to_o_width_ratio', 1.12),
            enable_code_char_classifier=settings.getboolean('enable_code_char_classifier', True),
            code_char_classifier_min_confidence=settings.getfloat('code_char_classifier_min_confidence', 0.72),
            code_char_classifier_min_margin=settings.getfloat('code_char_classifier_min_margin', 0.12),
            code_char_classifier_allow_leading_zero_to_o=settings.getboolean('code_char_classifier_allow_leading_zero_to_o', False),
            code_char_classifier_enable_width_vote=settings.getboolean('code_char_classifier_enable_width_vote', True),
            code_char_classifier_min_vote_support=settings.getint('code_char_classifier_min_vote_support', 2),
            code_char_classifier_max_positions=settings.getint('code_char_classifier_max_positions', 4),
            code_char_classifier_require_evidence=settings.getboolean('code_char_classifier_require_evidence', False),
            code_char_classifier_min_evidence_support=settings.getint('code_char_classifier_min_evidence_support', 2),
            code_char_tesseract_confidence_threshold=settings.getfloat('code_char_tesseract_confidence_threshold', 72.0),
            code_char_box_padding_ratio=settings.getfloat('code_char_box_padding_ratio', 0.18),
            enable_code_glyph_width_fallback=settings.getboolean('enable_code_glyph_width_fallback', False),
            enable_code_ambiguity_confirm_high_scale=settings.getboolean('enable_code_ambiguity_confirm_high_scale', True),
            code_ambiguity_confirm_scale=settings.getfloat('code_ambiguity_confirm_scale', 6.0),
            enable_code_ambiguity_full_ocr_confirm=settings.getboolean('enable_code_ambiguity_full_ocr_confirm', True),
            code_ambiguity_full_ocr_confirm_min_support=settings.getint('code_ambiguity_full_ocr_confirm_min_support', 2),
            enable_code_image_support_rescue=settings.getboolean('enable_code_image_support_rescue', True),
            code_image_support_min_votes=settings.getint('code_image_support_min_votes', 1),
            code_image_support_max_attempts=settings.getint('code_image_support_max_attempts', 6),
            code_box_alignment_ambiguity_pairs=settings.get('code_box_alignment_ambiguity_pairs', 'O:0,S:5,F:E,I:L'),
            code_box_alignment_min_match_ratio=settings.getfloat('code_box_alignment_min_match_ratio', 0.35),
            enable_code_anchor_rescue_pass=settings.getboolean('enable_code_anchor_rescue_pass', True),
            code_anchor_rescue_scale=settings.getfloat('code_anchor_rescue_scale', 7.5),
            code_anchor_rescue_only_on_no_char_boxes=settings.getboolean('code_anchor_rescue_only_on_no_char_boxes', True),
        )
        
        logger.info(f"Configuration loaded from: {config_path}")
        return config
