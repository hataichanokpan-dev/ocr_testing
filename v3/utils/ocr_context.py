"""
OCR Context - Thread-safe context for OCR operations
Replaces shared mutable state with immutable context objects
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OCRContext:
    """
    Immutable context for each OCR operation
    
    Fixes thread-safety issues from V2 where shared state was used:
    - self._current_debug_filename (V2 problem)
    - self._current_debug_page (V2 problem)
    
    By using frozen dataclass, we ensure:
    - Thread-safe: Each job has its own context
    - Immutable: Cannot be accidentally modified
    - Explicit: All data passed explicitly, no hidden state
    
    Attributes:
        filename: Original PDF filename
        page_num: Current page number (1-based)
        render_scale: Rendering scale factor (2.0, 3.0, 6.0)
        job_id: Unique job identifier for metrics tracking
    """
    
    filename: str
    page_num: int
    render_scale: float = 2.0
    job_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate context values"""
        if self.page_num < 1:
            raise ValueError(f"page_num must be >= 1, got {self.page_num}")
        
        if self.render_scale <= 0:
            raise ValueError(f"render_scale must be > 0, got {self.render_scale}")
    
    def with_scale(self, new_scale: float) -> 'OCRContext':
        """
        Create new context with different render scale
        
        Args:
            new_scale: New render scale factor
        
        Returns:
            OCRContext: New context with updated scale
        """
        return OCRContext(
            filename=self.filename,
            page_num=self.page_num,
            render_scale=new_scale,
            job_id=self.job_id
        )
    
    def with_job_id(self, job_id: str) -> 'OCRContext':
        """
        Create new context with job ID
        
        Args:
            job_id: Job identifier
        
        Returns:
            OCRContext: New context with job ID
        """
        return OCRContext(
            filename=self.filename,
            page_num=self.page_num,
            render_scale=self.render_scale,
            job_id=job_id
        )
