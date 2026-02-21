"""
PDF Splitter - Split PDFs based on header changes
Extracted from V2 with improvements
"""

import fitz  # PyMuPDF
import os
import re
import tempfile
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from v3.utils.config_manager import ExtractionConfig
from v3.components.header_validator import HeaderValidator
from v3.components.output_organizer import OutputOrganizer

logger = logging.getLogger(__name__)


class PdfSplitter:
    """
    Splits PDF files based on header text changes
    
    Features:
    - Detect header changes across pages
    - Create separate PDFs for each header group
    - Organized output with OutputOrganizer
    - Serial-based or similarity-based matching
    """
    
    def __init__(
        self,
        config: ExtractionConfig,
        validator: HeaderValidator,
        output_organizer: OutputOrganizer
    ):
        """
        Initialize PDF splitter
        
        Args:
            config: Extraction configuration
            validator: Header validator for comparison
            output_organizer: Output organizer for file paths
        """
        self.config = config
        self.validator = validator
        self.output_organizer = output_organizer
    
    def split_pdf(
        self,
        pdf_path: str,
        page_headers: List[Tuple[int, str]]
    ) -> List[Tuple[Path, str, Tuple[int, int]]]:
        """
        Split PDF based on header changes
        
        Args:
            pdf_path: Path to source PDF
            page_headers: List of (page_num, header_text) tuples
        
        Returns:
            List of (output_path, header_text, (start_page, end_page)) tuples
        """
        if not self.config.enable_pdf_splitting:
            logger.info("PDF splitting disabled in config")
            return []
        
        if len(page_headers) == 0:
            logger.warning("No headers provided for splitting")
            return []
        
        logger.info(f"Starting PDF split: {pdf_path}")
        
        # Detect header groups
        groups = self._detect_header_groups(page_headers)
        
        # Open source PDF
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            return []
        
        # If only one group, copy entire PDF to organized output
        if len(groups) <= 1:
            logger.info("Only one header group detected, copying entire PDF to organized output")
            try:
                # Get header text
                header_text = groups[0][2] if groups else "UNKNOWN"
                safe_header = self._sanitize_filename(header_text)
                
                # Generate filename
                original_name = Path(pdf_path).stem
                total_pages = len(doc)
                filename = self.config.split_naming_pattern.format(
                    header=safe_header,
                    start=1,
                    end=total_pages,
                    original=original_name,
                    index=1
                )
                
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                
                # Use deterministic target path; _create_pdf_subset handles
                # overwrite/lock fallback safely.
                output_path = self.output_organizer.get_output_path(filename)
                
                # Copy entire PDF
                saved_path = self._create_pdf_subset(doc, 0, total_pages - 1, output_path)
                
                doc.close()
                
                if saved_path:
                    logger.info(f"Copied PDF to: {saved_path} (header: {header_text})")
                    return [(saved_path, header_text, (0, total_pages - 1))]
                else:
                    return []
            except Exception as e:
                logger.error(f"Failed to copy PDF: {e}")
                doc.close()
                return []
        
        results = []
        original_name = Path(pdf_path).stem
        filename_counter = {}  # Track duplicate filenames
        
        # Create split PDFs
        for idx, (start_page, end_page, header_text) in enumerate(groups, 1):
            try:
                # Sanitize header for filename
                safe_header = self._sanitize_filename(header_text)
                
                # Generate base filename from pattern
                base_filename = self.config.split_naming_pattern.format(
                    header=safe_header,
                    start=start_page + 1,  # 1-based for display
                    end=end_page + 1,
                    original=original_name,
                    index=idx
                )
                
                if not base_filename.endswith('.pdf'):
                    base_filename += '.pdf'
                
                # Handle duplicate filenames
                filename = base_filename
                if safe_header in filename_counter:
                    # Duplicate detected - add suffix
                    filename_counter[safe_header] += 1
                    suffix = filename_counter[safe_header]
                    # Insert suffix before .pdf extension
                    filename = base_filename.replace('.pdf', f'_{suffix:02d}.pdf')
                    logger.warning(
                        f"Duplicate filename detected for header '{header_text}' - "
                        f"Using '{filename}' (pages {start_page + 1}-{end_page + 1})"
                    )
                else:
                    filename_counter[safe_header] = 1
                
                # Use deterministic target path; _create_pdf_subset handles
                # overwrite/lock fallback safely.
                output_path = self.output_organizer.get_output_path(filename)
                
                # Create new PDF with pages
                saved_path = self._create_pdf_subset(doc, start_page, end_page, output_path)
                
                if saved_path:
                    results.append((saved_path, header_text, (start_page, end_page)))
                    logger.info(
                        f"Created split PDF: {saved_path.name} "
                        f"(pages {start_page + 1}-{end_page + 1}, header: {header_text})"
                    )
            
            except Exception as e:
                logger.error(f"Failed to create split PDF for group {idx}: {e}")
        
        doc.close()
        
        logger.info(f"Split complete: created {len(results)} PDF(s)")
        return results
    
    def _detect_header_groups(
        self,
        page_headers: List[Tuple[int, str]]
    ) -> List[Tuple[int, int, str]]:
        """
        Detect groups of consecutive pages with same/similar headers
        
        Args:
            page_headers: List of (page_num, header_text) tuples
        
        Returns:
            List of (start_page, end_page, header_text) tuples (0-based page numbers)
        """
        if not page_headers:
            return []
        
        logger.debug(f"Detecting groups from {len(page_headers)} page headers")
        
        groups = []
        current_start = page_headers[0][0]
        current_header = page_headers[0][1]
        current_headers = [current_header]
        
        for i in range(1, len(page_headers)):
            page_num, header = page_headers[i]
            
            # Check if header matches current group
            if self.validator.headers_match(
                header,
                current_header,
                self.config.header_similarity_threshold
            ):
                # Same group
                current_headers.append(header)
            else:
                # New group - save previous
                best_header = self._select_best_header(current_headers)
                page_count = page_headers[i - 1][0] - current_start + 1
                logger.debug(f"Group: '{best_header}' pages {current_start+1}-{page_headers[i - 1][0]+1} ({page_count} pages)")
                groups.append((current_start, page_headers[i - 1][0], best_header))
                
                # Start new group
                current_start = page_num
                current_header = header
                current_headers = [header]
        
        # Add last group
        best_header = self._select_best_header(current_headers)
        page_count = page_headers[-1][0] - current_start + 1
        logger.debug(f"Group: '{best_header}' pages {current_start+1}-{page_headers[-1][0]+1} ({page_count} pages)")
        groups.append((current_start, page_headers[-1][0], best_header))

        # Apply conservative context correction (single-page OCR outliers).
        initial_group_count = len(groups)
        groups = self._apply_context_correction(groups)
        if len(groups) != initial_group_count:
            logger.info(
                f"Context correction merged {initial_group_count - len(groups)} group(s)"
            )

        logger.info(f"Detected {len(groups)} header groups")
        
        # Filter by min_pages_per_split (skip if min is 0)
        if self.config.min_pages_per_split > 0:
            filtered = []
            for start, end, header in groups:
                page_count = end - start + 1
                if page_count >= self.config.min_pages_per_split:
                    filtered.append((start, end, header))
                else:
                    logger.warning(f"Skipping group '{header}' with {page_count} pages (pages {start+1}-{end+1}, min: {self.config.min_pages_per_split})")
            logger.info(f"After filtering: {len(filtered)} groups (removed {len(groups) - len(filtered)})")
            return filtered
        else:
            logger.debug(f"No filtering (min=0), returning all {len(groups)} groups")
            return groups
    
    def _apply_context_correction(
        self,
        groups: List[Tuple[int, int, str]]
    ) -> List[Tuple[int, int, str]]:
        """
        Apply context-based correction to fix likely OCR errors
        
        Strategy:
        1. Find single-page groups surrounded by multi-page groups
        2. Check if the single-page header is similar to neighbors (serial number differs by 1-2 chars)
        3. Merge with the most similar neighbor
        
        Args:
            groups: List of (start_page, end_page, header_text) tuples
        
        Returns:
            Corrected list of groups (merged where OCR errors detected)
        """
        if len(groups) <= 1:
            return groups

        # Work on a mutable copy so we can merge a single-page group into the
        # next neighbor without index gymnastics.
        working = list(groups)
        corrected = []
        i = 0

        while i < len(working):
            current_start, current_end, current_header = working[i]
            current_pages = current_end - current_start + 1

            # Check if this is a single-page outlier.
            if current_pages == 1:
                prev_group = corrected[-1] if corrected else None
                next_group = working[i + 1] if i + 1 < len(working) else None

                prev_match = (
                    prev_group is not None
                    and self._is_likely_ocr_error(current_header, prev_group[2])
                )
                next_match = (
                    next_group is not None
                    and self._is_likely_ocr_error(current_header, next_group[2])
                )

                if prev_match or next_match:
                    merge_side = self._select_merge_side(
                        current_header=current_header,
                        prev_group=prev_group,
                        next_group=next_group,
                        prev_match=prev_match,
                        next_match=next_match,
                    )

                    if merge_side == "prev" and prev_group is not None:
                        prev_start, prev_end, prev_header = prev_group
                        logger.info(
                            f"Context correction: merged page {current_start + 1} "
                            f"('{current_header}') into previous group "
                            f"(pages {prev_start + 1}-{prev_end + 1}, '{prev_header}')"
                        )
                        corrected[-1] = (prev_start, current_end, prev_header)
                        i += 1
                        continue

                    if merge_side == "next" and next_group is not None:
                        next_start, next_end, next_header = next_group
                        logger.info(
                            f"Context correction: merged page {current_start + 1} "
                            f"('{current_header}') into next group "
                            f"(pages {next_start + 1}-{next_end + 1}, '{next_header}')"
                        )
                        working[i + 1] = (current_start, next_end, next_header)
                        i += 1
                        continue

            corrected.append((current_start, current_end, current_header))
            i += 1

        return self._merge_adjacent_groups(corrected)

    def _select_merge_side(
        self,
        current_header: str,
        prev_group: Optional[Tuple[int, int, str]],
        next_group: Optional[Tuple[int, int, str]],
        prev_match: bool,
        next_match: bool,
    ) -> Optional[str]:
        """
        Choose merge side for a single-page outlier.

        Preference:
        - if only one side matches, use that side
        - if both sides match, choose side with stronger neighbor confidence
        """
        if prev_match and not next_match:
            return "prev"
        if next_match and not prev_match:
            return "next"
        if not prev_match and not next_match:
            return None

        prev_rank = self._neighbor_rank(current_header, prev_group) if prev_group else -1
        next_rank = self._neighbor_rank(current_header, next_group) if next_group else -1
        return "next" if next_rank > prev_rank else "prev"

    def _neighbor_rank(
        self,
        current_header: str,
        neighbor_group: Optional[Tuple[int, int, str]],
    ) -> int:
        """
        Rank neighbor trustworthiness when both sides look mergeable.
        """
        if neighbor_group is None:
            return -1
        start, end, header = neighbor_group
        pages = end - start + 1
        score, normalized = self.validator.validate_and_score(header)
        strict_bonus = 20 if self.validator.is_strict_header(normalized if normalized else header) else 0
        return score + strict_bonus + min(10, pages)

    def _merge_adjacent_groups(
        self,
        groups: List[Tuple[int, int, str]]
    ) -> List[Tuple[int, int, str]]:
        """Merge adjacent groups that ended up with exactly the same header."""
        if not groups:
            return groups

        merged = [groups[0]]
        for start, end, header in groups[1:]:
            last_start, last_end, last_header = merged[-1]
            if start == last_end + 1 and header == last_header:
                merged[-1] = (last_start, end, last_header)
            else:
                merged.append((start, end, header))
        return merged
    
    def _is_likely_ocr_error(self, header1: str, header2: str) -> bool:
        """
        Check if two headers differ in a way that suggests OCR error
        
        Criteria for likely OCR error:
        1. Same prefix structure (B-XX-XXX-)
        2. Serial numbers differ by only 1-3 characters
        3. Overall similarity > 70%
        
        Special cases handled:
        - Missing separators (B-HK-FI4-S18008633 vs B-HK-FL4518008633)
        - Extra/missing characters in serial
        
        Args:
            header1: First header
            header2: Second header
        
        Returns:
            bool: True if likely an OCR error
        """
        # Never collapse two different strict-valid headers.
        _, norm1 = self.validator.validate_and_score(header1)
        _, norm2 = self.validator.validate_and_score(header2)
        strict1 = self.validator.is_strict_header(norm1 if norm1 else header1)
        strict2 = self.validator.is_strict_header(norm2 if norm2 else header2)
        if strict1 and strict2 and norm1 != norm2:
            # Allow a very specific strict-vs-strict repair:
            # same prefix + one serial is exactly the other with one trailing digit.
            # Example: R4092527 vs R40925274
            if self._is_serial_tail_digit_variant(norm1, norm2):
                return True
            return False

        # Quick check: if too different in length, not OCR error (unless missing separator)
        if abs(len(header1) - len(header2)) > 5:
            return False
        
        # Extract all digit sequences (potential serial numbers)
        import re
        digits1 = re.findall(r'\d+', header1)
        digits2 = re.findall(r'\d+', header2)
        
        # Find longest digit sequence (likely the serial number)
        longest_digits1 = max(digits1, key=len) if digits1 else ""
        longest_digits2 = max(digits2, key=len) if digits2 else ""
        
        # If serial numbers are identical or very similar, likely OCR error
        if longest_digits1 and longest_digits2:
            if len(longest_digits1) >= 7 and len(longest_digits2) >= 7:
                # Both have substantial serial numbers
                if longest_digits1 == longest_digits2:
                    # Exact match on serial = definitely OCR error in other parts
                    logger.debug(
                        f"Likely OCR error: serial numbers identical '{longest_digits1}' "
                        f"in '{header1}' vs '{header2}'"
                    )
                    return True
                
                # Check if one is substring of other (e.g., "18008633" vs "180086337")
                if longest_digits1 in longest_digits2 or longest_digits2 in longest_digits1:
                    if abs(len(longest_digits1) - len(longest_digits2)) <= 2:
                        logger.debug(
                            f"Likely OCR error: serial numbers very similar "
                            f"'{longest_digits1}' vs '{longest_digits2}'"
                        )
                        return True
                
                # Check edit distance on serial numbers
                serial_diff = self._count_char_differences(longest_digits1, longest_digits2)
                max_serial_len = max(len(longest_digits1), len(longest_digits2))
                if serial_diff <= 2 and serial_diff < max_serial_len * 0.25:
                    logger.debug(
                        f"Likely OCR error: serial numbers differ by {serial_diff} chars "
                        f"'{longest_digits1}' vs '{longest_digits2}'"
                    )
                    return True
        
        # Fallback to original structural check
        parts1 = header1.split(self.config.expected_separator)
        parts2 = header2.split(self.config.expected_separator)
        
        # Must have same number of parts (or differ by 1 due to missing separator)
        if abs(len(parts1) - len(parts2)) > 1:
            return False
        
        # Check if prefix parts are same (B-XX-XXX)
        if len(parts1) >= 3 and len(parts2) >= 3:
            # Prefix must match
            if parts1[0] != parts2[0]:
                return False
            
            # Country should match (or be close)
            if parts1[1] != parts2[1] and not self._strings_similar(parts1[1], parts2[1], 0.7):
                return False
            
            # Code can differ slightly (FI4 vs FL45)
            if not self._strings_similar(parts1[2], parts2[2], 0.5):
                # Allow if rest of header is very similar
                return False
            
            # Check serial number (last part)
            serial1 = parts1[-1] if len(parts1) > 3 else ""
            serial2 = parts2[-1] if len(parts2) > 3 else ""
            
            # Extract digits from serial
            serial_digits1 = ''.join(c for c in serial1 if c.isdigit())
            serial_digits2 = ''.join(c for c in serial2 if c.isdigit())
            
            if not serial_digits1 or not serial_digits2:
                return False
            
            # Count differing digits
            max_len = max(len(serial_digits1), len(serial_digits2))
            if max_len == 0:
                return False
            
            # Calculate Levenshtein-like distance
            diff_count = self._count_char_differences(serial_digits1, serial_digits2)
            
            # If digits differ by 1-3 chars and are mostly same, likely OCR error
            if diff_count <= 3 and diff_count < max_len * 0.3:
                logger.debug(
                    f"Likely OCR error detected: '{header1}' vs '{header2}' "
                    f"(serial digits: '{serial_digits1}' vs '{serial_digits2}', {diff_count} differences)"
                )
                return True
        
        return False

    def _is_serial_tail_digit_variant(self, header1: str, header2: str) -> bool:
        """
        Detect strict headers where one serial is the other plus one trailing digit.
        """
        if not header1 or not header2:
            return False

        parts1 = header1.split(self.config.expected_separator)
        parts2 = header2.split(self.config.expected_separator)
        if len(parts1) < 3 or len(parts2) < 3:
            return False

        prefix1 = parts1[:-1]
        prefix2 = parts2[:-1]
        if prefix1 != prefix2:
            return False

        serial1 = parts1[-1]
        serial2 = parts2[-1]
        if not serial1 or not serial2:
            return False

        if serial1[0] != serial2[0]:
            return False

        digits1 = "".join(c for c in serial1[1:] if c.isdigit())
        digits2 = "".join(c for c in serial2[1:] if c.isdigit())
        if not digits1 or not digits2:
            return False

        long_digits, short_digits = (digits1, digits2) if len(digits1) >= len(digits2) else (digits2, digits1)
        if len(long_digits) - len(short_digits) != 1:
            return False
        return long_digits.startswith(short_digits)
    
    def _strings_similar(self, s1: str, s2: str, threshold: float = 0.7) -> bool:
        """Check if two strings are similar above threshold"""
        if not s1 or not s2:
            return False
        
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return True
        
        diff = self._count_char_differences(s1, s2)
        similarity = 1.0 - (diff / max_len)
        return similarity >= threshold
    
    def _count_char_differences(self, s1: str, s2: str) -> int:
        """Count character differences between two strings (simple Levenshtein)"""
        len1, len2 = len(s1), len(s2)
        
        # Create distance matrix
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i-1][j],      # deletion
                        dp[i][j-1],      # insertion
                        dp[i-1][j-1]     # substitution
                    )
        
        return dp[len1][len2]
    
    def _select_best_header(self, headers: List[str]) -> str:
        """Select the best header from a list of similar headers"""
        if not headers:
            return ""

        if len(headers) == 1:
            score, corrected = self.validator.validate_and_score(headers[0])
            return corrected if score > 0 and corrected else headers[0]

        # Vote by normalized header first, then confidence.
        candidates: Dict[str, Dict[str, int]] = {}
        for header in headers:
            score, corrected = self.validator.validate_and_score(header)
            normalized = corrected if corrected else header
            strict_valid = self.validator.is_strict_header(normalized)

            if normalized not in candidates:
                candidates[normalized] = {
                    "count": 0,
                    "best_score": score,
                    "strict_valid": 1 if strict_valid else 0,
                }
            candidates[normalized]["count"] += 1
            candidates[normalized]["best_score"] = max(
                candidates[normalized]["best_score"], score
            )
            if strict_valid:
                candidates[normalized]["strict_valid"] = 1

        ranked = sorted(
            candidates.items(),
            key=lambda item: (
                item[1]["count"],
                item[1]["strict_valid"],
                item[1]["best_score"],
                len(item[0]),
                item[0],
            ),
            reverse=True,
        )
        return ranked[0][0]
    
    def _create_pdf_subset(
        self,
        source_doc: fitz.Document,
        start_page: int,
        end_page: int,
        output_path: Path
    ) -> Optional[Path]:
        """
        Create new PDF from page range
        
        Args:
            source_doc: Source document
            start_page: Start page (0-based, inclusive)
            end_page: End page (0-based, inclusive)
            output_path: Output file path
        
        Returns:
            Optional[Path]: Saved path if successful, None if failed
        """
        temp_path: Optional[Path] = None
        new_doc: Optional[fitz.Document] = None
        try:
            # Create new document
            new_doc = fitz.open()
            
            # Insert pages
            new_doc.insert_pdf(
                source_doc,
                from_page=start_page,
                to_page=end_page
            )
            
            # Save to temp file first, then atomically replace target to avoid
            # permission issues when destination file already exists/locked.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fd, raw_temp_path = tempfile.mkstemp(
                suffix=".tmp.pdf",
                prefix=f"{output_path.stem}_",
                dir=str(output_path.parent)
            )
            os.close(fd)
            temp_path = Path(raw_temp_path)
            new_doc.save(str(temp_path))
            new_doc.close()
            new_doc = None
            if not temp_path.exists():
                raise FileNotFoundError(f"Temp file not created: {temp_path}")

            target = output_path
            retry_delays = [0.0, 0.2, 0.6]
            for delay in retry_delays:
                try:
                    if delay > 0:
                        time.sleep(delay)
                    os.replace(str(temp_path), str(target))
                    return target
                except PermissionError:
                    continue
                except FileNotFoundError:
                    # Temp file disappeared unexpectedly (e.g. external lock/cleanup).
                    # Break to regeneration flow.
                    break

            # Temp file disappeared before replace; regenerate subset.
            if not temp_path.exists():
                regen_target = target
                if regen_target.exists():
                    regen_target = self.output_organizer.get_unique_output_path(
                        f"{output_path.stem}_regen{output_path.suffix}"
                    )
                regen_doc = fitz.open()
                try:
                    regen_doc.insert_pdf(
                        source_doc,
                        from_page=start_page,
                        to_page=end_page
                    )
                    regen_doc.save(str(regen_target))
                    logger.warning(
                        f"Temp file missing during replace, regenerated subset: {regen_target.name}"
                    )
                    return regen_target
                finally:
                    regen_doc.close()

            # Final fallback: write to alternate filename if target is locked
            fallback_target = self.output_organizer.get_unique_output_path(
                f"{output_path.stem}_locked{output_path.suffix}"
            )
            if temp_path.exists():
                os.replace(str(temp_path), str(fallback_target))
            else:
                # Regenerate subset directly to fallback path as a last resort.
                regen_doc = fitz.open()
                try:
                    regen_doc.insert_pdf(
                        source_doc,
                        from_page=start_page,
                        to_page=end_page
                    )
                    regen_doc.save(str(fallback_target))
                finally:
                    regen_doc.close()
            logger.warning(
                f"Target file was locked, saved to fallback path: {fallback_target.name}"
            )
            return fallback_target

        except Exception as e:
            logger.error(f"Failed to create PDF subset: {e}")
            return None
        finally:
            if new_doc is not None:
                try:
                    new_doc.close()
                except Exception:
                    pass
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
    
    def _sanitize_filename(self, text: str) -> str:
        """Convert text to safe filename"""
        if not text:
            return "unnamed"
        
        # Remove or replace invalid characters
        if self.config.remove_special_chars:
            text = re.sub(r'[^\w\s-]', '', text)
        
        # Replace spaces
        text = text.replace(' ', self.config.replace_spaces_with)
        
        # Remove multiple consecutive separators
        text = re.sub(r'[_-]+', '_', text)
        
        # Trim to max length
        text = text[:self.config.max_filename_length]
        
        # Remove leading/trailing separators
        text = text.strip('_-')
        
        return text if text else "unnamed"
