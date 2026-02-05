"""
Extraction Logger - Async API logging with circuit breaker
Non-blocking logging to prevent API issues from blocking processing
"""

import queue
import threading
import time
import logging
import requests
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Simple circuit breaker pattern for API calls
    
    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying again (OPEN -> HALF_OPEN)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)"""
        with self._lock:
            if self.state == 'OPEN':
                # Check if timeout elapsed -> move to HALF_OPEN
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = 'HALF_OPEN'
                    logger.info("Circuit breaker: OPEN -> HALF_OPEN (testing recovery)")
                    return False
                return True
            return False
    
    def record_success(self):
        """Record successful request"""
        with self._lock:
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED (service recovered)")
            
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed request"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == 'HALF_OPEN':
                # Failed during testing -> back to OPEN
                self.state = 'OPEN'
                logger.warning("Circuit breaker: HALF_OPEN -> OPEN (service still failing)")
            
            elif self.failure_count >= self.failure_threshold:
                # Too many failures -> OPEN
                self.state = 'OPEN'
                logger.warning(
                    f"Circuit breaker: CLOSED -> OPEN "
                    f"({self.failure_count} failures, blocking API calls for {self.timeout}s)"
                )


class ExtractionLogger:
    """
    Non-blocking API logger with queue and circuit breaker
    
    Features:
    - Async fire-and-forget logging (doesn't block processing)
    - Queue-based buffering
    - Circuit breaker to handle API failures gracefully
    - Background worker thread
    - Automatic cleanup on shutdown
    """
    
    def __init__(
        self,
        api_url: str,
        enabled: bool = True,
        async_mode: bool = True,
        queue_size: int = 1000,
        timeout: int = 5,
        circuit_breaker_threshold: int = 5
    ):
        """
        Initialize extraction logger
        
        Args:
            api_url: API endpoint URL
            enabled: Enable/disable logging
            async_mode: Use async queue (True) or blocking (False)
            queue_size: Maximum queue size
            timeout: Request timeout in seconds
            circuit_breaker_threshold: Failures before circuit opens
        """
        self.api_url = api_url
        self.enabled = enabled
        self.async_mode = async_mode
        self.timeout = timeout
        
        # Queue for async logging
        self.queue = queue.Queue(maxsize=queue_size) if async_mode else None
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout=60
        )
        
        # Statistics
        self.total_sent = 0
        self.total_success = 0
        self.total_failed = 0
        self.total_dropped = 0
        
        # Worker thread for async mode
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        
        if async_mode:
            self.worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="ExtractionLogger-Worker"
            )
            self.worker_thread.start()
            logger.info(f"ExtractionLogger started in async mode (queue_size: {queue_size})")
        else:
            logger.info("ExtractionLogger started in blocking mode")
    
    def log_extraction(
        self,
        original_filename: str,
        page_number: int,
        method_results: Dict,
        direct_text: str = "",
        direct_score: int = 0,
        final_answer: str = "",
        debug_image_path: str = "",
        status: str = "success",
        error_message: str = ""
    ):
        """
        Log extraction result to API
        
        Args:
            original_filename: PDF filename
            page_number: Page number
            method_results: OCR method results dict
            direct_text: Text from direct extraction
            direct_score: Score for direct extraction
            final_answer: Final selected text
            debug_image_path: Path to debug image
            status: Processing status
            error_message: Error message if any
        """
        if not self.enabled:
            return
        
        # Build payload
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_filename": original_filename,
            "page_number": page_number,
            "method0_text": method_results.get('method0', {}).get('text', ''),
            "method0_score": method_results.get('method0', {}).get('score', 0),
            "method0B_text": method_results.get('method0B', {}).get('text', ''),
            "method0B_score": method_results.get('method0B', {}).get('score', 0),
            "method0C_text": method_results.get('method0C', {}).get('text', ''),
            "method0C_score": method_results.get('method0C', {}).get('score', 0),
            "method1_text": method_results.get('method1', {}).get('text', ''),
            "method1_score": method_results.get('method1', {}).get('score', 0),
            "method2_text": method_results.get('method2', {}).get('text', ''),
            "method2_score": method_results.get('method2', {}).get('score', 0),
            "method3_text": method_results.get('method3', {}).get('text', ''),
            "method3_score": method_results.get('method3', {}).get('score', 0),
            "method4_text": method_results.get('method4', {}).get('text', ''),
            "method4_score": method_results.get('method4', {}).get('score', 0),
            "method5_text": method_results.get('method5', {}).get('text', ''),
            "method5_score": method_results.get('method5', {}).get('score', 0),
            "method6_text": method_results.get('method6', {}).get('text', ''),
            "method6_score": method_results.get('method6', {}).get('score', 0),
            "method7_text": method_results.get('method7', {}).get('text', ''),
            "method7_score": method_results.get('method7', {}).get('score', 0),
            "direct_text": direct_text,
            "direct_score": direct_score,
            "status": status,
            "error_message": error_message,
            "debug_image_path": debug_image_path,
            "finnal_answer": final_answer  # Note: API uses 'finnal' (typo in API)
        }
        
        if self.async_mode:
            # Async: add to queue
            try:
                self.queue.put_nowait(payload)
            except queue.Full:
                self.total_dropped += 1
                logger.warning(f"Log queue full, dropping message (total dropped: {self.total_dropped})")
        else:
            # Blocking: send immediately
            self._send_to_api(payload)
    
    def _worker(self):
        """Background worker thread for async logging"""
        logger.debug("Extraction logger worker started")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for payload with timeout
                payload = self.queue.get(timeout=1)
                self._send_to_api(payload)
                self.queue.task_done()
            
            except queue.Empty:
                continue
            
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
        
        logger.debug("Extraction logger worker stopped")
    
    def _send_to_api(self, payload: Dict):
        """
        Send payload to API endpoint
        
        Args:
            payload: Data to send
        """
        if self.circuit_breaker.is_open():
            self.total_dropped += 1
            logger.debug("Circuit breaker open, dropping log message")
            return
        
        self.total_sent += 1
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={
                    'accept': '*/*',
                    'Content-Type': 'application/json'
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                self.total_success += 1
                self.circuit_breaker.record_success()
                logger.debug(f"API log sent successfully (total: {self.total_success})")
            else:
                self.total_failed += 1
                self.circuit_breaker.record_failure()
                logger.warning(f"API returned status {response.status_code}")
        
        except requests.exceptions.Timeout:
            self.total_failed += 1
            self.circuit_breaker.record_failure()
            logger.warning(f"API request timed out after {self.timeout}s")
        
        except requests.exceptions.ConnectionError:
            self.total_failed += 1
            self.circuit_breaker.record_failure()
            logger.warning(f"Could not connect to API at {self.api_url}")
        
        except Exception as e:
            self.total_failed += 1
            self.circuit_breaker.record_failure()
            logger.error(f"API logging failed: {e}")
    
    def get_stats(self) -> Dict:
        """Get logging statistics"""
        return {
            'enabled': self.enabled,
            'async_mode': self.async_mode,
            'total_sent': self.total_sent,
            'total_success': self.total_success,
            'total_failed': self.total_failed,
            'total_dropped': self.total_dropped,
            'success_rate': (self.total_success / self.total_sent * 100) if self.total_sent > 0 else 0.0,
            'circuit_breaker_state': self.circuit_breaker.state,
            'queue_size': self.queue.qsize() if self.async_mode else 0
        }
    
    def shutdown(self, timeout: int = 10):
        """
        Gracefully shutdown logger
        
        Args:
            timeout: Max seconds to wait for queue to empty
        """
        if not self.async_mode:
            return
        
        logger.info("Shutting down extraction logger...")
        
        # Wait for queue to empty
        start_time = time.time()
        while not self.queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        # Signal worker to stop
        self.shutdown_event.set()
        
        # Wait for worker thread
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        
        # Log final stats
        stats = self.get_stats()
        logger.info(
            f"Extraction logger stopped: "
            f"sent={stats['total_sent']}, "
            f"success={stats['total_success']}, "
            f"failed={stats['total_failed']}, "
            f"dropped={stats['total_dropped']}"
        )
