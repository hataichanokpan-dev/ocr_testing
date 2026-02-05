"""
Output Organizer - Manages folder structure: Year/Date/Files
Handles automatic folder creation and cleanup of old files
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class OutputOrganizer:
    """
    จัดการ output folder structure: {base_dir}/{YYYY}/{YYYY-MM-DD}/files
    
    Features:
    - Auto-create year and date folders
    - Cleanup old files based on retention policy
    - Thread-safe folder creation
    - Unique filename generation
    
    Example:
        organizer = OutputOrganizer('output')
        path = organizer.get_output_path('B-HK-WFE-S17975643.pdf')
        # Returns: output/2026/2026-02-05/B-HK-WFE-S17975643.pdf
    """
    
    def __init__(self, base_output_dir: str = "output", retention_days: int = 90):
        """
        Initialize output organizer
        
        Args:
            base_output_dir: Base directory for all outputs
            retention_days: Number of days to keep files (0 = keep forever)
        """
        self.base_dir = Path(base_output_dir)
        self.retention_days = retention_days
        
        # Create base directory if not exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"OutputOrganizer initialized: {self.base_dir.absolute()}")
        logger.info(f"Retention policy: {retention_days} days" if retention_days > 0 else "Retention policy: Keep forever")
    
    def get_output_path(self, filename: str, processing_date: Optional[datetime] = None) -> Path:
        """
        Generate organized output path with year and date folders
        
        Args:
            filename: Output filename (e.g., 'B-HK-WFE-S17975643.pdf')
            processing_date: Date for folder organization (default: today)
        
        Returns:
            Path: Full path with folder structure (e.g., output/2026/2026-02-05/filename.pdf)
        """
        if processing_date is None:
            processing_date = datetime.now()
        
        # Create folder structure: YYYY/YYYY-MM-DD
        year = str(processing_date.year)
        date_str = processing_date.strftime('%Y-%m-%d')
        
        output_dir = self.base_dir / year / date_str
        output_dir.mkdir(parents=True, exist_ok=True)
        
        full_path = output_dir / filename
        
        logger.debug(f"Generated output path: {full_path}")
        return full_path
    
    def get_unique_output_path(self, filename: str, processing_date: Optional[datetime] = None) -> Path:
        """
        Generate unique output path (add counter if file exists)
        
        Args:
            filename: Desired filename
            processing_date: Date for folder organization (default: today)
        
        Returns:
            Path: Unique path (e.g., filename_1.pdf, filename_2.pdf)
        """
        base_path = self.get_output_path(filename, processing_date)
        
        if not base_path.exists():
            return base_path
        
        # File exists - add counter
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        
        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                logger.debug(f"Generated unique path: {new_path}")
                return new_path
            counter += 1
    
    def cleanup_old_files(self) -> Tuple[int, int]:
        """
        Clean up files older than retention policy
        
        Returns:
            Tuple[int, int]: (deleted_folders_count, deleted_files_count)
        """
        if self.retention_days <= 0:
            logger.info("Cleanup skipped: retention policy disabled")
            return 0, 0
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_folders = 0
        deleted_files = 0
        
        logger.info(f"Starting cleanup: removing files older than {cutoff_date.strftime('%Y-%m-%d')}")
        
        try:
            # Iterate through year folders
            for year_folder in self.base_dir.iterdir():
                if not year_folder.is_dir() or not year_folder.name.isdigit():
                    continue
                
                # Iterate through date folders
                for date_folder in year_folder.iterdir():
                    if not date_folder.is_dir():
                        continue
                    
                    # Parse date from folder name (YYYY-MM-DD)
                    try:
                        folder_date = datetime.strptime(date_folder.name, '%Y-%m-%d')
                        
                        if folder_date < cutoff_date:
                            # Count files before deletion
                            file_count = sum(1 for _ in date_folder.rglob('*') if _.is_file())
                            
                            # Delete entire date folder
                            shutil.rmtree(date_folder)
                            deleted_folders += 1
                            deleted_files += file_count
                            logger.info(f"Deleted old folder: {date_folder} ({file_count} files)")
                    
                    except ValueError:
                        logger.warning(f"Invalid date folder name: {date_folder.name}")
                        continue
                
                # Remove empty year folder
                if year_folder.is_dir() and not any(year_folder.iterdir()):
                    year_folder.rmdir()
                    logger.info(f"Removed empty year folder: {year_folder}")
            
            logger.info(f"Cleanup completed: {deleted_folders} folders, {deleted_files} files deleted")
            return deleted_folders, deleted_files
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            return deleted_folders, deleted_files
    
    def get_folder_stats(self) -> dict:
        """
        Get statistics about organized folders
        
        Returns:
            dict: Statistics (total_files, total_size_mb, folder_count, oldest_date, newest_date)
        """
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0.0,
            'folder_count': 0,
            'oldest_date': None,
            'newest_date': None,
            'years': {}
        }
        
        try:
            date_folders = []
            
            for year_folder in self.base_dir.iterdir():
                if not year_folder.is_dir() or not year_folder.name.isdigit():
                    continue
                
                year = year_folder.name
                stats['years'][year] = {'folders': 0, 'files': 0, 'size_mb': 0.0}
                
                for date_folder in year_folder.iterdir():
                    if not date_folder.is_dir():
                        continue
                    
                    try:
                        folder_date = datetime.strptime(date_folder.name, '%Y-%m-%d')
                        date_folders.append(folder_date)
                        
                        # Count files and size in this folder
                        folder_files = 0
                        folder_size = 0
                        
                        for file_path in date_folder.rglob('*'):
                            if file_path.is_file():
                                folder_files += 1
                                folder_size += file_path.stat().st_size
                        
                        stats['total_files'] += folder_files
                        stats['total_size_bytes'] += folder_size
                        stats['folder_count'] += 1
                        
                        stats['years'][year]['folders'] += 1
                        stats['years'][year]['files'] += folder_files
                        stats['years'][year]['size_mb'] += folder_size / (1024 * 1024)
                    
                    except ValueError:
                        continue
            
            stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
            
            if date_folders:
                stats['oldest_date'] = min(date_folders).strftime('%Y-%m-%d')
                stats['newest_date'] = max(date_folders).strftime('%Y-%m-%d')
            
            return stats
        
        except Exception as e:
            logger.error(f"Failed to get folder stats: {e}")
            return stats
    
    def list_files_by_date(self, target_date: datetime) -> List[Path]:
        """
        List all files in a specific date folder
        
        Args:
            target_date: Target date to list
        
        Returns:
            List[Path]: List of file paths
        """
        year = str(target_date.year)
        date_str = target_date.strftime('%Y-%m-%d')
        
        target_folder = self.base_dir / year / date_str
        
        if not target_folder.exists():
            return []
        
        return [f for f in target_folder.iterdir() if f.is_file()]
