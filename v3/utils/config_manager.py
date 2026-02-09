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
    
    # OCR optimization
    ocr_filter_black_text: bool = True
    ocr_black_threshold: int = 100
    
    # OCR Enhancement (V3.1 - Full Upgrade)
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
            
            # OCR optimization
            ocr_filter_black_text=settings.getboolean('ocr_filter_black_text', True),
            ocr_black_threshold=settings.getint('ocr_black_threshold', 100),
            
            # OCR Enhancement (V3.1)
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
        )
        
        logger.info(f"Configuration loaded from: {config_path}")
        return config
