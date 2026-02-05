"""
Performance Metrics Tracker
Tracks processing time, accuracy rate, API success rate
"""

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for a single processing job"""
    job_id: str
    filename: str
    start_time: float
    end_time: Optional[float] = None
    total_pages: int = 0
    processed_pages: int = 0
    ocr_attempts: int = 0
    ocr_successful: int = 0
    best_score: int = 0
    api_calls: int = 0
    api_success: int = 0
    api_failures: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def processing_time_seconds(self) -> float:
        """Calculate processing time"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Calculate OCR success rate"""
        if self.ocr_attempts == 0:
            return 0.0
        return (self.ocr_successful / self.ocr_attempts) * 100
    
    @property
    def api_success_rate(self) -> float:
        """Calculate API success rate"""
        if self.api_calls == 0:
            return 0.0
        return (self.api_success / self.api_calls) * 100
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'job_id': self.job_id,
            'filename': self.filename,
            'processing_time_seconds': round(self.processing_time_seconds, 2),
            'total_pages': self.total_pages,
            'processed_pages': self.processed_pages,
            'ocr_attempts': self.ocr_attempts,
            'ocr_successful': self.ocr_successful,
            'success_rate': round(self.success_rate, 2),
            'best_score': self.best_score,
            'api_calls': self.api_calls,
            'api_success': self.api_success,
            'api_failures': self.api_failures,
            'api_success_rate': round(self.api_success_rate, 2),
            'errors_count': len(self.errors),
            'errors': self.errors[:5]  # Only first 5 errors
        }


class MetricsTracker:
    """
    Track performance metrics across all processing jobs
    
    Features:
    - Track processing time per job
    - Track OCR success rate
    - Track API success rate
    - Generate summary statistics
    - Export metrics to JSON
    """
    
    def __init__(self, enable_tracking: bool = True):
        """
        Initialize metrics tracker
        
        Args:
            enable_tracking: Enable/disable metrics tracking
        """
        self.enable_tracking = enable_tracking
        self.jobs: Dict[str, ProcessingMetrics] = {}
        self.completed_jobs: List[ProcessingMetrics] = []
        
        # Aggregate statistics
        self.total_processing_time = 0.0
        self.total_ocr_attempts = 0
        self.total_ocr_successful = 0
        self.total_api_calls = 0
        self.total_api_success = 0
        
        logger.info(f"MetricsTracker initialized (enabled: {enable_tracking})")
    
    def start_job(self, job_id: str, filename: str, total_pages: int = 0) -> ProcessingMetrics:
        """
        Start tracking a new job
        
        Args:
            job_id: Unique job identifier
            filename: PDF filename being processed
            total_pages: Total number of pages
        
        Returns:
            ProcessingMetrics: Metrics object for this job
        """
        if not self.enable_tracking:
            return None
        
        metrics = ProcessingMetrics(
            job_id=job_id,
            filename=filename,
            start_time=time.time(),
            total_pages=total_pages
        )
        
        self.jobs[job_id] = metrics
        logger.debug(f"Started tracking job: {job_id} ({filename})")
        
        return metrics
    
    def end_job(self, job_id: str) -> Optional[ProcessingMetrics]:
        """
        End tracking for a job
        
        Args:
            job_id: Job identifier
        
        Returns:
            ProcessingMetrics: Completed metrics
        """
        if not self.enable_tracking or job_id not in self.jobs:
            return None
        
        metrics = self.jobs[job_id]
        metrics.end_time = time.time()
        
        # Move to completed jobs
        self.completed_jobs.append(metrics)
        del self.jobs[job_id]
        
        # Update aggregates
        self.total_processing_time += metrics.processing_time_seconds
        self.total_ocr_attempts += metrics.ocr_attempts
        self.total_ocr_successful += metrics.ocr_successful
        self.total_api_calls += metrics.api_calls
        self.total_api_success += metrics.api_success
        
        logger.info(
            f"Job completed: {job_id} | "
            f"Time: {metrics.processing_time_seconds:.2f}s | "
            f"OCR: {metrics.ocr_successful}/{metrics.ocr_attempts} | "
            f"API: {metrics.api_success}/{metrics.api_calls}"
        )
        
        return metrics
    
    def record_ocr_attempt(self, job_id: str, successful: bool, score: int = 0):
        """Record an OCR attempt"""
        if not self.enable_tracking or job_id not in self.jobs:
            return
        
        metrics = self.jobs[job_id]
        metrics.ocr_attempts += 1
        
        if successful:
            metrics.ocr_successful += 1
            metrics.best_score = max(metrics.best_score, score)
    
    def record_api_call(self, job_id: str, successful: bool):
        """Record an API call"""
        if not self.enable_tracking or job_id not in self.jobs:
            return
        
        metrics = self.jobs[job_id]
        metrics.api_calls += 1
        
        if successful:
            metrics.api_success += 1
        else:
            metrics.api_failures += 1
    
    def record_error(self, job_id: str, error_message: str):
        """Record an error"""
        if not self.enable_tracking or job_id not in self.jobs:
            return
        
        metrics = self.jobs[job_id]
        metrics.errors.append(error_message)
    
    def get_summary(self) -> dict:
        """
        Get summary statistics
        
        Returns:
            dict: Summary statistics
        """
        total_jobs = len(self.completed_jobs)
        
        if total_jobs == 0:
            return {
                'total_jobs': 0,
                'active_jobs': len(self.jobs),
                'avg_processing_time_seconds': 0.0,
                'total_processing_time_seconds': 0.0,
                'total_ocr_attempts': 0,
                'total_ocr_successful': 0,
                'ocr_success_rate': 0.0,
                'total_api_calls': 0,
                'total_api_success': 0,
                'api_success_rate': 0.0,
                'fastest_job': 0.0,
                'slowest_job': 0.0
            }
        
        avg_time = self.total_processing_time / total_jobs
        ocr_rate = (self.total_ocr_successful / self.total_ocr_attempts * 100) if self.total_ocr_attempts > 0 else 0.0
        api_rate = (self.total_api_success / self.total_api_calls * 100) if self.total_api_calls > 0 else 0.0
        
        return {
            'total_jobs': total_jobs,
            'active_jobs': len(self.jobs),
            'avg_processing_time_seconds': round(avg_time, 2),
            'total_processing_time_seconds': round(self.total_processing_time, 2),
            'total_ocr_attempts': self.total_ocr_attempts,
            'total_ocr_successful': self.total_ocr_successful,
            'ocr_success_rate': round(ocr_rate, 2),
            'total_api_calls': self.total_api_calls,
            'total_api_success': self.total_api_success,
            'api_success_rate': round(api_rate, 2),
            'fastest_job': min((m.processing_time_seconds for m in self.completed_jobs), default=0),
            'slowest_job': max((m.processing_time_seconds for m in self.completed_jobs), default=0),
        }
    
    def export_to_json(self, filepath: str):
        """
        Export metrics to JSON file
        
        Args:
            filepath: Output JSON file path
        """
        try:
            data = {
                'summary': self.get_summary(),
                'timestamp': datetime.now().isoformat(),
                'completed_jobs': [m.to_dict() for m in self.completed_jobs[-100:]]  # Last 100 jobs
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Metrics exported to: {filepath}")
        
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
    
    def print_summary(self):
        """Print summary to console"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("PERFORMANCE METRICS SUMMARY")
        print("="*60)
        print(f"Total Jobs Completed: {summary['total_jobs']}")
        print(f"Active Jobs: {summary['active_jobs']}")
        print(f"Average Processing Time: {summary['avg_processing_time_seconds']:.2f}s")
        print(f"Total Processing Time: {summary['total_processing_time_seconds']:.2f}s")
        print(f"\nOCR Performance:")
        print(f"  Success Rate: {summary['ocr_success_rate']:.2f}%")
        print(f"  Total Attempts: {summary['total_ocr_attempts']}")
        print(f"  Successful: {summary['total_ocr_successful']}")
        print(f"\nAPI Performance:")
        print(f"  Success Rate: {summary['api_success_rate']:.2f}%")
        print(f"  Total Calls: {summary['total_api_calls']}")
        print(f"  Successful: {summary['total_api_success']}")
        print(f"\nPerformance Range:")
        print(f"  Fastest Job: {summary['fastest_job']:.2f}s")
        print(f"  Slowest Job: {summary['slowest_job']:.2f}s")
        print("="*60 + "\n")
