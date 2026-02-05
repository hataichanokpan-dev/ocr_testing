"""
Debug Image Manager - Manages debug image saving and cleanup
"""

import logging
import cv2
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DebugImageManager:
    """
    Manages debug image storage and cleanup
    
    Features:
    - Organized storage by date
    - Automatic cleanup of old images
    - Unique filename generation
    """
    
    def __init__(
        self,
        base_folder: str = "debug_images",
        organize_by_date: bool = True,
        retention_days: int = 30,
        enabled: bool = True
    ):
        """
        Initialize debug image manager
        
        Args:
            base_folder: Base folder for debug images
            organize_by_date: Organize images by date
            retention_days: Days to keep images (0 = forever)
            enabled: Enable/disable debug image saving
        """
        self.base_folder = Path(base_folder)
        self.organize_by_date = organize_by_date
        self.retention_days = retention_days
        self.enabled = enabled
        
        if self.enabled:
            self.base_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Debug images folder: {self.base_folder.absolute()}")
            
            # Cleanup old images
            if self.retention_days > 0:
                self.cleanup_old_images()
    
    def get_debug_path(
        self,
        original_filename: str,
        page_num: int,
        method_name: str = ""
    ) -> Optional[Path]:
        """
        Generate debug image path
        
        Args:
            original_filename: Original PDF filename
            page_num: Page number
            method_name: OCR method name
        
        Returns:
            Path: Full path for debug image, or None if disabled
        """
        if not self.enabled:
            return None
        
        try:
            # Organize by date if enabled
            if self.organize_by_date:
                date_str = datetime.now().strftime('%Y-%m-%d')
                save_folder = self.base_folder / date_str
            else:
                save_folder = self.base_folder
            
            save_folder.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%H%M%S")
            filename_base = Path(original_filename).stem if original_filename else "unknown"
            
            if method_name:
                filename = f"{filename_base}_page{page_num}_{method_name}_{timestamp}.png"
            else:
                filename = f"{filename_base}_page{page_num}_{timestamp}.png"
            
            return save_folder / filename
        
        except Exception as e:
            logger.error(f"Failed to generate debug path: {e}")
            return Path(f"debug_page{page_num}.png")
    
    def save_image(
        self,
        image,
        original_filename: str,
        page_num: int,
        method_name: str = ""
    ) -> Optional[Path]:
        """
        Save debug image
        
        Args:
            image: Image to save (numpy array or PIL Image)
            original_filename: Original PDF filename
            page_num: Page number
            method_name: OCR method name
        
        Returns:
            Path: Saved file path, or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            debug_path = self.get_debug_path(original_filename, page_num, method_name)
            if debug_path is None:
                return None
            
            cv2.imwrite(str(debug_path), image)
            logger.debug(f"Saved debug image: {debug_path}")
            return debug_path
        
        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")
            return None
    
    def cleanup_old_images(self) -> int:
        """
        Clean up images older than retention days
        
        Returns:
            int: Number of files deleted
        """
        if self.retention_days <= 0:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        try:
            for file_path in self.base_folder.rglob('*.png'):
                try:
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_time < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
                
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old debug images")
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup old images: {e}")
            return deleted_count
