#!/usr/bin/env python3
"""
Academic Paper Release Script v2.0

This script provides a complete pipeline for converting academic papers
from markdown to publication-ready PDFs with customizable formatting,
attachments, and cleanup.

Features:
    - Complete markdown to PDF pipeline
    - Citation processing and reference filtering
    - Configurable formatting (Typst/LaTeX)
    - Front/back page attachments
    - Progress reporting and error recovery
    - Dry-run mode for testing
    - Comprehensive logging

Usage:
    python release.py paper.md                    # Basic release with defaults
    python release.py paper.md --config release.json  # Custom config
    python release.py paper.md --format typst    # Specify format
    python release.py paper.md --output final.pdf # Custom output
    python release.py paper.md --dry-run         # Preview what would happen
    python release.py --create-config            # Create default config file
    python release.py --check-deps               # Check system dependencies
"""

import os
import re
import json
import argparse
import subprocess
import tempfile
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Try to import yaml, fallback gracefully
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('release.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Import our existing functionality with error handling
try:
    from paper_converter import (
        extract_citations_from_file,
        load_references,
        match_citation_to_reference,
        generate_filtered_references,
        remove_references_section,
        combine_paper_and_references,
        convert_with_pandoc
    )
    logger.info("Successfully imported paper_converter")
except ImportError as e:
    logger.error(f"Failed to import paper_converter: {e}")
    print("ERROR: paper_converter.py not found. Please ensure it's in the same directory.")
    exit(1)

try:
    from pdf_assembler import (
        detect_file_format,
        convert_to_pdf,
        merge_pdfs
    )
    logger.info("Successfully imported pdf_assembler")
except ImportError as e:
    logger.error(f"Failed to import pdf_assembler: {e}")
    print("ERROR: pdf_assembler.py not found. Please ensure it's in the same directory.")
    exit(1)

# Version information
__version__ = "2.0.0"
__author__ = "Academic Paper Tools"

class ReleaseConfig:
    """Configuration class for release settings with validation."""

    def __init__(self, config_file: Optional[str] = None, validate: bool = True):
        self.config = self._load_defaults()
        self.errors: List[str] = []

        if config_file:
            self._load_config_file(config_file)

        if validate:
            self._validate_config()

    def _load_defaults(self) -> Dict[str, Any]:
        """Load default configuration with comprehensive options."""
        return {
            "format": "typst",  # typst or latex
            "preamble": {
                "typst": "typst_preamble.typ",
                "latex": None
            },
            "output": {
                "filename": None,  # Auto-generated if None
                "directory": "releases",
                "overwrite_existing": False,
                "backup_existing": True
            },
            "attachments": {
                "front": [],  # List of files to attach at front
                "end": []     # List of files to attach at end
            },
            "cleanup": {
                "intermediate_files": True,
                "temp_files": True,
                "keep_logs": False,
                "backup_directory": "backups"
            },
            "processing": {
                "max_retries": 2,
                "timeout": 300,  # seconds
                "verbose": False
            },
            "citations": {
                "strategy": "filter",  # filter, merge, keep
                "strict_matching": True,  # require exact matches for citations
                "include_missing": False,  # include missing citations as comments
                "case_sensitive": False,  # case sensitivity for author matching
                "fuzzy_matching": True   # enable fuzzy/approximate matching
            },
            "metadata": {
                "author": "Unknown",
                "title": "Academic Paper",
                "version": "1.0",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "keywords": [],
                "abstract": None
            }
        }

    def _load_config_file(self, config_file: str) -> None:
        """Load configuration from JSON or YAML file with error handling."""
        config_path = Path(config_file)
        if not config_path.exists():
            logger.warning(f"Config file '{config_file}' not found, using defaults")
            return

        if not config_path.is_file():
            logger.error(f"Config path '{config_file}' is not a file")
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    if not HAS_YAML:
                        raise ImportError("PyYAML not available for YAML config files. Install with: pip install PyYAML")
                    file_config = yaml.safe_load(f)
                else:  # Assume JSON
                    file_config = json.load(f)

            if not isinstance(file_config, dict):
                raise ValueError("Config file must contain a JSON object/dictionary")

            # Deep merge the config
            self._deep_merge(self.config, file_config)
            logger.info(f"Loaded configuration from {config_file}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file '{config_file}': {e}")
            self.errors.append(f"Invalid JSON syntax: {e}")
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config file '{config_file}': {e}")
            self.errors.append(f"Invalid YAML syntax: {e}")
        except Exception as e:
            logger.error(f"Error loading config file '{config_file}': {e}")
            self.errors.append(f"Config file error: {e}")

    def _validate_config(self) -> None:
        """Validate configuration values with detailed error messages."""
        # Validate format
        valid_formats = ['typst', 'latex']
        format_value = self.get('format')
        if format_value not in valid_formats:
            self.errors.append(f"Invalid format '{format_value}'. Must be one of: {', '.join(valid_formats)}")

        # Validate output directory
        output_dir = self.get('output.directory')
        if output_dir is not None:
            if not isinstance(output_dir, str):
                self.errors.append("output.directory must be a string")
            elif output_dir.strip() == "":
                self.errors.append("output.directory cannot be empty")

        # Validate filename
        filename = self.get('output.filename')
        if filename is not None:
            if not isinstance(filename, str):
                self.errors.append("output.filename must be a string")
            elif '/' in filename or '\\' in filename:
                self.errors.append("output.filename should not contain path separators")

        # Validate attachments
        for attach_type in ['front', 'end']:
            attachments = self.get(f'attachments.{attach_type}', [])
            if not isinstance(attachments, list):
                self.errors.append(f"attachments.{attach_type} must be a list")
                continue

            for i, attachment in enumerate(attachments):
                if not isinstance(attachment, str):
                    self.errors.append(f"Attachment {i} in {attach_type} must be a string (filename)")
                elif attachment.strip() == "":
                    self.errors.append(f"Attachment {i} in {attach_type} cannot be empty")

        # Validate processing options
        max_retries = self.get('processing.max_retries', 2)
        if not isinstance(max_retries, int) or max_retries < 0:
            self.errors.append("processing.max_retries must be a non-negative integer")
        elif max_retries > 10:
            self.errors.append("processing.max_retries seems too high (>10), may indicate configuration issue")

        timeout = self.get('processing.timeout', 300)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            self.errors.append("processing.timeout must be a positive number")
        elif timeout > 3600:  # 1 hour
            self.errors.append("processing.timeout seems too high (>3600s), may indicate configuration issue")

        # Validate preamble files
        for fmt in ['typst', 'latex']:
            preamble = self.get(f'preamble.{fmt}')
            if preamble is not None:
                if not isinstance(preamble, str):
                    self.errors.append(f"preamble.{fmt} must be a string (filename)")
                elif preamble.strip() == "":
                    self.errors.append(f"preamble.{fmt} cannot be empty")

        # Validate metadata
        metadata = self.get('metadata', {})
        if not isinstance(metadata, dict):
            self.errors.append("metadata must be a dictionary")
        else:
            # Check specific metadata fields
            if 'title' in metadata and not isinstance(metadata['title'], str):
                self.errors.append("metadata.title must be a string")
            if 'author' in metadata and not isinstance(metadata['author'], str):
                self.errors.append("metadata.author must be a string")

        # Validate citations configuration
        citations = self.get('citations', {})
        if not isinstance(citations, dict):
            self.errors.append("citations must be a dictionary")
        else:
            # Validate strategy
            valid_strategies = ['filter', 'merge', 'keep']
            strategy = citations.get('strategy', 'filter')
            if strategy not in valid_strategies:
                self.errors.append(f"citations.strategy must be one of: {', '.join(valid_strategies)}")

            # Validate boolean options
            bool_options = ['strict_matching', 'case_sensitive', 'fuzzy_matching', 'include_missing']
            for option in bool_options:
                if option in citations and not isinstance(citations[option], bool):
                    self.errors.append(f"citations.{option} must be a boolean")

        # Cross-validation
        format_type = self.get('format')
        preamble_file = self.get(f'preamble.{format_type}')
        if preamble_file and not Path(preamble_file).exists():
            self.errors.append(f"Preamble file for {format_type} not found: {preamble_file}")

        # Check backup directory
        backup_dir = self.get('cleanup.backup_directory')
        if backup_dir and not isinstance(backup_dir, str):
            self.errors.append("cleanup.backup_directory must be a string")

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Deep merge two dictionaries with type checking."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with dot notation support."""
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value with dot notation support."""
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.errors) == 0

    def get_errors(self) -> List[str]:
        """Get list of configuration errors."""
        return self.errors.copy()

    def save(self, filepath: str) -> bool:
        """Save current configuration to file."""
        try:
            config_path = Path(filepath)
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    if HAS_YAML:
                        yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
                    else:
                        raise ImportError("PyYAML required for YAML output")
                else:
                    json.dump(self.config, f, indent=2, sort_keys=False)

            logger.info(f"Configuration saved to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config to {filepath}: {e}")
            return False

class PaperRelease:
    """Main class for handling paper releases with comprehensive error handling."""

    def __init__(self, config: ReleaseConfig):
        self.config = config
        self.temp_files: List[Path] = []
        self.intermediate_files: List[Path] = []
        self.backup_files: List[Tuple[Path, Path]] = []  # (original, backup) pairs
        self.start_time = None

    def release(self, input_file: str, output_file: Optional[str] = None, dry_run: bool = False) -> Optional[Path]:
        """Execute the complete release pipeline."""
        self.start_time = datetime.now()

        try:
            # Validate inputs
            input_path = self._validate_input(input_file)
            output_path = self._prepare_output_path(input_path, output_file)

            # Check for existing output and backup if needed
            if output_path.exists() and not dry_run:
                self._backup_existing_file(output_path)

            if dry_run:
                return self._dry_run(input_path, output_path)

            logger.info("Starting Academic Paper Release Pipeline")
            logger.info(f"Input: {input_file}")
            logger.info(f"Output: {output_path}")
            logger.info(f"Format: {self.config.get('format')}")
            logger.info(f"Config: {len(self.config.get_errors())} validation errors")

            # Step 1: Convert markdown to target format
            target_file = self._convert_paper(input_path)

            # Step 2: Generate PDF with attachments
            final_pdf = self._generate_pdf(target_file, output_path)

            # Step 3: Add metadata if configured
            self._add_metadata(final_pdf)

            # Step 4: Validate final output
            self._validate_output(final_pdf)

            # Step 5: Cleanup
            self._cleanup()

            duration = datetime.now() - self.start_time
            logger.info(f"SUCCESS! Release complete in {duration.total_seconds():.1f}s")
            logger.info(f"Final PDF: {final_pdf} ({final_pdf.stat().st_size} bytes)")

            return final_pdf

        except Exception as e:
            duration = datetime.now() - self.start_time if self.start_time else 0
            logger.error(f"Release failed after {duration.total_seconds():.1f}s: {e}")

            # Attempt cleanup on failure
            try:
                self._cleanup()
            except Exception as cleanup_error:
                logger.error(f"Cleanup also failed: {cleanup_error}")

            raise

    def _validate_input(self, input_file: str) -> Path:
        """Validate input file and return Path object with comprehensive checks."""
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_file}")

        # Check file extension
        if input_path.suffix.lower() != '.md':
            logger.warning(f"Input file '{input_file}' does not have .md extension. Proceeding anyway.")

        # Check file readability and encoding
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                # Try to read first few lines to validate encoding
                lines = f.readlines(1000)  # Read first 1000 chars worth of lines
                if not lines:
                    raise ValueError(f"Input file appears to be empty: {input_file}")
        except UnicodeDecodeError:
            # Try alternative encodings
            for encoding in ['utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    with open(input_path, 'r', encoding=encoding) as f:
                        f.read(1000)
                    logger.warning(f"File uses {encoding} encoding instead of UTF-8")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Cannot read input file with any supported encoding: {input_file}")
        except PermissionError:
            raise PermissionError(f"Cannot read input file (permission denied): {input_file}")
        except Exception as e:
            raise ValueError(f"Error reading input file: {e}")

        # Check file size
        file_size = input_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Input file is empty: {input_file}")

        max_size = 100 * 1024 * 1024  # 100MB limit
        if file_size > max_size:
            raise ValueError(f"Input file too large ({file_size} bytes, max {max_size}): {input_file}")

        # Check if references.md exists
        refs_path = Path('references.md')
        if not refs_path.exists():
            raise FileNotFoundError("references.md not found in current directory")

        # Validate references.md readability
        try:
            with open(refs_path, 'r', encoding='utf-8') as f:
                f.read(1000)  # Quick readability check
        except Exception as e:
            logger.warning(f"Warning: Cannot validate references.md readability: {e}")

        logger.info(f"Input validation passed: {input_path} ({file_size} bytes)")
        return input_path

    def _prepare_output_path(self, input_path: Path, output_file: Optional[str]) -> Path:
        """Prepare and validate output path."""
        if output_file:
            output_path = Path(output_file)
        else:
            base_name = self.config.get('output.filename')
            if not base_name:
                # Auto-generate from input filename
                base_name = input_path.stem.replace('_', '-').replace(' ', '-')

            output_dir = Path(self.config.get('output.directory', 'releases'))
            output_path = output_dir / f"{base_name}.pdf"

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        return output_path

    def _backup_existing_file(self, file_path: Path) -> None:
        """Backup existing file if configured."""
        if not self.config.get('output.backup_existing', True):
            return

        backup_dir = Path(self.config.get('cleanup.backup_directory', 'backups'))
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        try:
            import shutil
            shutil.copy2(file_path, backup_path)
            self.backup_files.append((file_path, backup_path))
            logger.info(f"Backed up existing file: {file_path} -> {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to backup {file_path}: {e}")

    def _dry_run(self, input_path: Path, output_path: Path) -> None:
        """Perform a dry run showing what would happen."""
        print("DRY RUN - Preview of Release Pipeline")
        print("=" * 60)
        print(f"Input file: {input_path} ({input_path.stat().st_size} bytes)")
        print(f"Output file: {output_path}")
        print(f"Format: {self.config.get('format')}")
        format_type = self.config.get('format')
        print(f"Preamble: {self.config.get(f'preamble.{format_type}')}")

        # Check attachments
        front_attachments = self.config.get('attachments.front', [])
        end_attachments = self.config.get('attachments.end', [])

        if front_attachments:
            print(f"Front attachments: {len(front_attachments)} files")
            for attachment in front_attachments:
                status = "[OK]" if Path(attachment).exists() else "[MISSING]"
                print(f"  {status} {attachment}")

        if end_attachments:
            print(f"End attachments: {len(end_attachments)} files")
            for attachment in end_attachments:
                status = "[OK]" if Path(attachment).exists() else "[MISSING]"
                print(f"  {status} {attachment}")

        # Check output directory
        if output_path.exists():
            print(f"WARNING: Output file exists: {output_path}")
            if self.config.get('output.backup_existing'):
                print("  -> Will create backup")
            else:
                print("  -> Will overwrite")
        else:
            print(f"OK: Output directory ready: {output_path.parent}")

        # Check citation configuration
        citations = self.config.get('citations', {})
        strategy = citations.get('strategy', 'filter')
        print(f"Citation Strategy: {strategy}")
        if strategy == 'filter':
            print("  -> Include only cited references")
        elif strategy == 'merge':
            print("  -> Include all references (mark cited ones)")
        elif strategy == 'keep':
            print("  -> Keep existing references section")

        # Check cleanup settings
        cleanup = self.config.get('cleanup', {})
        print(f"Cleanup: intermediate={cleanup.get('intermediate_files', True)}, temp={cleanup.get('temp_files', True)}")

        print("\nPipeline Steps:")
        print("1. Extract citations from markdown")
        print(f"2. Process references.md ({strategy} strategy)")
        print("3. Combine paper with processed references")
        print("4. Convert to target format (Typst/LaTeX)")
        print("5. Generate PDF from formatted document")
        print("6. Attach front/end documents if specified")
        print("7. Merge all PDFs into final document")
        print("8. Cleanup intermediate files")

        print("\nSUCCESS: Dry run complete - no files were modified")
        return None

    def _convert_paper(self, input_path: Path) -> Path:
        """Convert markdown to target format (Typst/LaTeX) with comprehensive error handling."""
        logger.info("Converting markdown to target format...")

        # Validate input file
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        # Check file size (reasonable limit)
        file_size = input_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Input file is empty: {input_path}")
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError(f"Input file too large ({file_size} bytes): {input_path}")

        max_retries = self.config.get('processing.max_retries', 2)

        for attempt in range(max_retries + 1):
            try:
                # Step 1: Extract citations with error handling
                logger.info("Extracting citations...")
                try:
                    citations = extract_citations_from_file(str(input_path))
                    logger.info(f"Found {len(citations)} citations")
                except Exception as e:
                    logger.error(f"Failed to extract citations: {e}")
                    raise RuntimeError(f"Citation extraction failed: {e}")

                if not citations:
                    logger.warning("No citations found in input file - proceeding anyway")

                # Step 2: Load and process references with error handling
                logger.info("Loading and processing references...")
                try:
                    references = load_references()
                    logger.info(f"Loaded {len(references)} reference entries")
                except Exception as e:
                    logger.error(f"Failed to load references: {e}")
                    raise RuntimeError(f"Reference loading failed: {e}")

                # Get citation configuration
                citation_config = self.config.get('citations', {
                    'strategy': 'filter',
                    'strict_matching': True,
                    'case_sensitive': False,
                    'fuzzy_matching': True,
                    'include_missing': False
                })

                filtered_refs_file = input_path.with_stem(f"{input_path.stem}_refs_filtered")
                try:
                    strategy = citation_config.get('strategy', 'filter')
                    num_refs, num_missing = generate_filtered_references(citations, references, str(filtered_refs_file), strategy, citation_config)
                    logger.info(f"Generated {num_refs} references (strategy: {strategy})")
                    if num_missing > 0:
                        logger.warning(f"{num_missing} citations not found in references.md")
                except Exception as e:
                    logger.error(f"Failed to generate references: {e}")
                    raise RuntimeError(f"Reference processing failed: {e}")

                # Verify filtered references file was created
                if not Path(filtered_refs_file).exists():
                    raise FileNotFoundError(f"Failed to create filtered references file: {filtered_refs_file}")

                # Step 3: Combine paper and references with error handling
                logger.info("Combining paper with filtered references...")
                combined_file = input_path.with_stem(f"{input_path.stem}_combined")
                try:
                    combine_paper_and_references(str(input_path), str(filtered_refs_file), str(combined_file))
                except Exception as e:
                    logger.error(f"Failed to combine paper and references: {e}")
                    raise RuntimeError(f"File combination failed: {e}")

                # Verify combined file was created and has content
                combined_path = Path(combined_file)
                if not combined_path.exists():
                    raise FileNotFoundError(f"Failed to create combined file: {combined_file}")

                combined_size = combined_path.stat().st_size
                if combined_size == 0:
                    raise ValueError(f"Combined file is empty: {combined_file}")

                logger.info(f"Combined file created: {combined_size} bytes")

                # Step 4: Convert to target format with comprehensive error handling
                format_type = self.config.get('format')
                preamble_file = self.config.get(f'preamble.{format_type}')

                logger.info(f"Converting to {format_type} format...")
                target_file = combined_path.with_suffix(f'.{format_type}')

                # Check preamble file if specified
                if preamble_file:
                    preamble_path = Path(preamble_file)
                    if not preamble_path.exists():
                        logger.warning(f"Preamble file not found: {preamble_file}")
                        preamble_file = None
                    elif not preamble_path.is_file():
                        logger.warning(f"Preamble path is not a file: {preamble_file}")
                        preamble_file = None

                # Use pandoc for conversion with timeout and error handling
                timeout = self.config.get('processing.timeout', 300)
                try:
                    success, error = self._run_with_timeout(
                        lambda: convert_with_pandoc(str(combined_file), str(target_file), format_type, preamble_file),
                        timeout
                    )
                except Exception as e:
                    logger.error(f"Pandoc conversion timed out or failed: {e}")
                    raise RuntimeError(f"Format conversion failed: {e}")

                if not success:
                    error_msg = error.strip() if error else "Unknown error"
                    logger.error(f"Pandoc conversion failed: {error_msg}")
                    raise RuntimeError(f"Format conversion failed: {error_msg}")

                # Verify target file was created and has content
                target_path = Path(target_file)
                if not target_path.exists():
                    raise FileNotFoundError(f"Conversion did not create target file: {target_file}")

                target_size = target_path.stat().st_size
                if target_size == 0:
                    raise ValueError(f"Target file is empty: {target_file}")

                logger.info(f"Target file created: {target_size} bytes")

                # Track intermediate files
                self.intermediate_files.extend([Path(filtered_refs_file), combined_path])

                logger.info(f"Successfully converted to {format_type}: {target_file}")
                return target_path

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    # Clean up any partial files from this attempt
                    self._cleanup_attempt_files()
                    # Add small delay before retry
                    import time
                    time.sleep(1)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")
                    raise

    def _run_with_timeout(self, func, timeout: float):
        """Run a function with timeout."""
        import threading
        import queue

        result_queue = queue.Queue()

        def wrapper():
            try:
                result = func()
                result_queue.put(('success', result))
            except Exception as e:
                result_queue.put(('error', e))

        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise TimeoutError(f"Operation timed out after {timeout} seconds")

        if result_queue.empty():
            raise RuntimeError("Operation completed but no result returned")

        status, result = result_queue.get()
        if status == 'error':
            raise result

        return result

    def _generate_pdf(self, target_file: Path, output_path: Path) -> Path:
        """Generate PDF from target file with attachments and comprehensive error handling."""
        logger.info("Generating PDF with attachments...")

        # Validate target file
        if not target_file.exists():
            raise FileNotFoundError(f"Target file not found: {target_file}")

        if not target_file.is_file():
            raise ValueError(f"Target path is not a file: {target_file}")

        target_size = target_file.stat().st_size
        if target_size == 0:
            raise ValueError(f"Target file is empty: {target_file}")

        # Collect all files to merge with validation
        files_to_merge = []
        missing_attachments = []
        invalid_attachments = []

        # Add front attachments with validation
        front_files = self.config.get('attachments.front', [])
        for front_file in front_files:
            try:
                front_path = Path(front_file)
                if not front_path.exists():
                    missing_attachments.append(f"front: {front_file}")
                    logger.warning(f"Front attachment not found: {front_file}")
                    continue
                if not front_path.is_file():
                    invalid_attachments.append(f"front: {front_file} (not a file)")
                    logger.warning(f"Front attachment is not a file: {front_file}")
                    continue
                files_to_merge.append(front_path)
                logger.info(f"Adding front attachment: {front_file}")
            except Exception as e:
                logger.warning(f"Error processing front attachment {front_file}: {e}")

        # Add main file
        files_to_merge.append(target_file)
        logger.info(f"Main document: {target_file}")

        # Add end attachments with validation
        end_files = self.config.get('attachments.end', [])
        for end_file in end_files:
            try:
                end_path = Path(end_file)
                if not end_path.exists():
                    missing_attachments.append(f"end: {end_file}")
                    logger.warning(f"End attachment not found: {end_file}")
                    continue
                if not end_path.is_file():
                    invalid_attachments.append(f"end: {end_file} (not a file)")
                    logger.warning(f"End attachment is not a file: {end_file}")
                    continue
                files_to_merge.append(end_path)
                logger.info(f"Adding end attachment: {end_file}")
            except Exception as e:
                logger.warning(f"Error processing end attachment {end_file}: {e}")

        # Report attachment issues
        if missing_attachments:
            logger.warning(f"Missing attachments: {', '.join(missing_attachments)}")
        if invalid_attachments:
            logger.error(f"Invalid attachments: {', '.join(invalid_attachments)}")
            if not self.config.get('processing.continue_on_attachment_errors', False):
                raise ValueError(f"Invalid attachments found: {', '.join(invalid_attachments)}")

        if not files_to_merge:
            raise ValueError("No valid files to process")

        # Convert all to PDFs with comprehensive error handling
        pdf_files = []
        for file_path in files_to_merge:
            try:
                format_type = detect_file_format(file_path)
                if format_type == 'pdf':
                    pdf_files.append(file_path)
                    logger.debug(f"Using existing PDF: {file_path}")
                elif format_type in ['typst', 'latex']:
                    # Convert to PDF
                    logger.info(f"Converting {file_path.name} ({format_type}) to PDF...")
                    pdf_file = file_path.with_suffix('.pdf')

                    # Use timeout for conversion
                    timeout = self.config.get('processing.timeout', 300)
                    try:
                        result_pdf = self._run_with_timeout(
                            lambda: convert_to_pdf(file_path, pdf_file),
                            timeout
                        )
                        pdf_files.append(result_pdf)
                        self.temp_files.append(result_pdf)
                        logger.info(f"Converted to PDF: {result_pdf}")
                    except Exception as e:
                        logger.error(f"PDF conversion failed for {file_path}: {e}")
                        raise RuntimeError(f"Failed to convert {file_path} to PDF: {e}")
                else:
                    raise ValueError(f"Unsupported file format for {file_path}: {format_type}")

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                raise

        # Validate we have PDF files to work with
        if not pdf_files:
            raise ValueError("No PDF files were successfully prepared")

        # Merge PDFs with error handling
        try:
            if len(pdf_files) == 1:
                # Just copy single file
                import shutil
                shutil.copy2(pdf_files[0], output_path)
                logger.info(f"Copied single PDF to: {output_path}")
            else:
                logger.info(f"Merging {len(pdf_files)} PDF files...")
                merge_pdfs(pdf_files, output_path)
                logger.info(f"Merged PDFs into: {output_path}")

            # Validate output
            if not output_path.exists():
                raise FileNotFoundError(f"PDF generation did not create output file: {output_path}")

            output_size = output_path.stat().st_size
            if output_size == 0:
                raise ValueError(f"Generated PDF is empty: {output_path}")

            logger.info(f"PDF generation successful: {output_size} bytes")
            return output_path

        except Exception as e:
            logger.error(f"PDF merging/generation failed: {e}")
            raise

    def _add_metadata(self, pdf_path: Path) -> None:
        """Add metadata to the final PDF if configured."""
        metadata = self.config.get('metadata', {})
        if not metadata or not any(metadata.values()):
            return

        logger.info("Adding metadata to PDF...")

        # This would require additional PDF manipulation libraries
        # For now, just log what metadata would be added
        metadata_info = []
        if metadata.get('title'):
            metadata_info.append(f"Title: {metadata['title']}")
        if metadata.get('author'):
            metadata_info.append(f"Author: {metadata['author']}")
        if metadata.get('keywords'):
            metadata_info.append(f"Keywords: {', '.join(metadata['keywords'])}")

        if metadata_info:
            logger.info(f"Metadata to add: {'; '.join(metadata_info)}")
            logger.warning("PDF metadata addition not yet implemented - requires additional libraries")

    def _validate_output(self, pdf_path: Path) -> None:
        """Validate the final PDF output."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"Final PDF was not created: {pdf_path}")

        file_size = pdf_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Final PDF is empty: {pdf_path}")

        min_expected_size = 1000  # 1KB minimum for a valid PDF
        if file_size < min_expected_size:
            logger.warning(f"Final PDF seems very small ({file_size} bytes): {pdf_path}")

        logger.info(f"Validated final PDF: {pdf_path} ({file_size} bytes)")

    def _cleanup_attempt_files(self) -> None:
        """Clean up files from a failed attempt."""
        # Clean up any intermediate files created in this attempt
        current_intermediates = []
        for file_path in self.intermediate_files:
            if file_path.exists():
                try:
                    file_path.unlink()
                    current_intermediates.append(file_path)
                except OSError:
                    pass

        if current_intermediates:
            logger.debug(f"Cleaned up {len(current_intermediates)} intermediate files from failed attempt")

    def _cleanup(self) -> None:
        """Clean up temporary and intermediate files with comprehensive error handling."""
        logger.info("Starting cleanup...")

        cleanup_stats = {'intermediate': 0, 'temp': 0, 'errors': 0}

        # Clean up intermediate files
        if self.config.get('cleanup.intermediate_files', True):
            for file_path in self.intermediate_files:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        cleanup_stats['intermediate'] += 1
                        logger.debug(f"Cleaned up intermediate file: {file_path.name}")
                except OSError as e:
                    logger.warning(f"Failed to clean up intermediate file {file_path}: {e}")
                    cleanup_stats['errors'] += 1

        # Clean up temporary files
        if self.config.get('cleanup.temp_files', True):
            for file_path in self.temp_files:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        cleanup_stats['temp'] += 1
                        logger.debug(f"Cleaned up temp file: {file_path.name}")
                except OSError as e:
                    logger.warning(f"Failed to clean up temp file {file_path}: {e}")
                    cleanup_stats['errors'] += 1

        logger.info(f"Cleanup complete: {cleanup_stats['intermediate']} intermediate, {cleanup_stats['temp']} temp files removed")
        if cleanup_stats['errors'] > 0:
            logger.warning(f"Cleanup had {cleanup_stats['errors']} errors")

        if self.config.get('cleanup.temp_files'):
            for file_path in self.temp_files:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        print(f"Cleaned up temp file: {file_path.name}")
                except OSError:
                    pass

def check_dependencies() -> Dict[str, bool]:
    """Check for required system dependencies with fallbacks."""
    deps = {}

    # Check Python modules
    try:
        import paper_converter
        deps['paper_converter'] = True
    except ImportError:
        deps['paper_converter'] = False

    try:
        import pdf_assembler
        deps['pdf_assembler'] = True
    except ImportError:
        deps['pdf_assembler'] = False

    # Check external tools with timeout and error handling
    tools = ['pandoc', 'typst', 'pdflatex']
    for tool in tools:
        try:
            # Use different version commands for different tools
            if tool == 'pandoc':
                cmd = [tool, '--version']
            elif tool == 'typst':
                cmd = [tool, '--version']
            else:  # pdflatex
                cmd = [tool, '--version']

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            deps[tool] = result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking {tool}")
            deps[tool] = False
        except FileNotFoundError:
            deps[tool] = False
        except subprocess.SubprocessError as e:
            logger.warning(f"Error checking {tool}: {e}")
            deps[tool] = False
        except Exception as e:
            logger.warning(f"Unexpected error checking {tool}: {e}")
            deps[tool] = False

    # Check PDF tools with fallbacks
    pdf_tools = ['pdftk', 'pdfunite']
    pdf_tool_found = False
    for tool in pdf_tools:
        try:
            if tool == 'pdftk':
                cmd = [tool, '--version']
            else:  # pdfunite
                cmd = [tool, '--version']

            result = subprocess.run(cmd, capture_output=True, timeout=10)
            deps[tool] = result.returncode == 0
            if deps[tool]:
                pdf_tool_found = True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            deps[tool] = False
        except Exception as e:
            logger.warning(f"Error checking {tool}: {e}")
            deps[tool] = False

    # Check for alternative PDF tools
    alt_pdf_tools = ['gs', 'magick']  # Ghostscript, ImageMagick
    for tool in alt_pdf_tools:
        try:
            result = subprocess.run([tool, '--version'], capture_output=True, timeout=10)
            deps[tool] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            deps[tool] = False

    # Overall PDF capability
    deps['pdf_tools_available'] = pdf_tool_found or any(deps.get(tool, False) for tool in alt_pdf_tools)

    return deps

def print_dependency_status(deps: Dict[str, bool]) -> None:
    """Print dependency check results."""
    print("Dependency Check Results:")
    print("-" * 40)

    all_good = True

    # Python modules
    print("Python Modules:")
    for module in ['paper_converter', 'pdf_assembler']:
        status = "[OK]" if deps.get(module, False) else "[MISSING]"
        print(f"  {status} {module}")
        if not deps.get(module, False):
            all_good = False

    # External tools
    print("\nExternal Tools:")
    for tool in ['pandoc', 'typst', 'pdflatex']:
        status = "[OK]" if deps.get(tool, False) else "[MISSING]"
        print(f"  {status} {tool}")
        if not deps.get(tool, False):
            all_good = False

    # PDF tools (optional)
    print("\nPDF Tools (optional - improves merging):")
    pdf_tools_found = 0
    for tool in ['pdftk', 'pdfunite']:
        status = "[OK]" if deps.get(tool, False) else "[MISSING]"
        print(f"  {status} {tool}")
        if deps.get(tool, False):
            pdf_tools_found += 1

    # Check for PDF merging capability
    pdf_capable = deps.get('pdf_tools_available', False)
    if not pdf_capable:
        print("\nWARNING: No PDF merging tools found. Manual merging may be required.")
        print("   Install pdftk, pdfunite, or ensure pypdf is available for automatic PDF merging.")
        print("   Alternative: Use 'pip install pypdf' for Python-based PDF handling.")

    # Overall assessment
    critical_missing = [dep for dep in ['paper_converter', 'pdf_assembler', 'pandoc'] if not deps.get(dep, False)]
    recommended_missing = [dep for dep in ['typst', 'pdflatex'] if not deps.get(dep, False)]

    if critical_missing:
        print(f"\nERROR: Critical dependencies missing: {', '.join(critical_missing)}")
        print("   These are required for basic functionality.")
    elif not pdf_capable:
        print(f"\nWARNING: PDF merging tools missing. Single-file processing will work,")
        print("   but multi-file merging will require manual intervention.")
    elif recommended_missing:
        print(f"\nINFO: Some recommended tools missing: {', '.join(recommended_missing)}")
        print("   Functionality will be limited but basic operations should work.")
    else:
        print("\nSUCCESS: All dependencies satisfied!")

    return all_good and pdf_capable

def create_default_config(output_file: str = "release_config.json") -> bool:
    """Create a default configuration file."""
    try:
        config = ReleaseConfig(validate=False)  # Don't validate defaults

        success = config.save(output_file)
        if success:
            print(f"Created default config file: {output_file}")
            print("   Edit this file to customize your release settings.")
        return success

    except Exception as e:
        print(f"ERROR: Failed to create config file: {e}")
        return False

def main():
    """Main entry point with comprehensive error handling."""
    parser = argparse.ArgumentParser(
        prog='release.py',
        description='Academic Paper Release Pipeline v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
   python release.py paper.md                           # Basic release with defaults
   python release.py paper.md --config release.json     # Custom config
   python release.py paper.md --format latex            # LaTeX output
   python release.py paper.md --output final.pdf        # Custom output
   python release.py paper.md --citation-strategy merge # Include all references
   python release.py paper.md --citation-strategy keep  # Keep existing references
   python release.py paper.md --dry-run                 # Preview what would happen
   python release.py --create-config                    # Create default config file
   python release.py --check-deps                       # Check dependencies

CONFIG FILE FORMAT (JSON):
{
  "format": "typst",
  "preamble": {
    "typst": "typst_preamble.typ",
    "latex": null
  },
  "output": {
    "filename": "my_paper",
    "directory": "releases",
    "backup_existing": true
  },
  "attachments": {
    "front": ["cover.pdf"],
    "end": ["appendix.pdf"]
  },
  "cleanup": {
    "intermediate_files": true,
    "temp_files": true
  },
  "processing": {
    "max_retries": 2,
    "timeout": 300
  }
}

For more information, see the documentation in AGENTS.md and CLAUDE.md.
        """
    )

    parser.add_argument('input_file', nargs='?', help='Input markdown file')
    parser.add_argument('--config', '-c', help='Configuration file (JSON/YAML)')
    parser.add_argument('--format', choices=['typst', 'latex'], help='Output format (overrides config)')
    parser.add_argument('--output', '-o', help='Output PDF file (overrides config)')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Preview actions without executing')
    parser.add_argument('--create-config', action='store_true', help='Create default config file and exit')
    parser.add_argument('--check-deps', action='store_true', help='Check system dependencies and exit')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files (overrides config)')
    parser.add_argument('--citation-strategy', choices=['filter', 'merge', 'keep'],
                        help='Citation/reference strategy: filter (cited only), merge (all), keep (existing)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--version', action='version', version=f'Academic Paper Release v{__version__}')

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle special actions
    if args.create_config:
        return 0 if create_default_config() else 1

    if args.check_deps:
        deps = check_dependencies()
        print_dependency_status(deps)
        return 0

    # Validate input file
    if not args.input_file:
        parser.error("Input file is required (or use --create-config/--check-deps)")

    # Check dependencies
    deps = check_dependencies()
    critical_deps = ['paper_converter', 'pdf_assembler', 'pandoc']
    missing_critical = [dep for dep in critical_deps if not deps.get(dep, False)]

    if missing_critical:
        print(f"ERROR: Critical dependencies missing: {', '.join(missing_critical)}")
        print("Run 'python release.py --check-deps' for detailed status.")
        return 1

    # Warn about PDF capabilities
    if not deps.get('pdf_tools_available', False):
        logger.warning("No PDF merging tools available - multi-file operations may require manual intervention")

    # Load configuration
    try:
        config = ReleaseConfig(args.config)
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return 1

    # Check config validity
    if not config.is_valid():
        print("ERROR: Configuration validation errors:")
        for error in config.get_errors():
            print(f"  - {error}")
        return 1

    # Override config with command-line args
    if args.format:
        config.set('format', args.format)
    if args.output:
        config.set('output.filename', Path(args.output).stem)
    if args.keep_temp:
        config.set('cleanup.temp_files', False)
    if args.citation_strategy:
        config.set('citations.strategy', args.citation_strategy)

    # Execute release with comprehensive error handling
    try:
        releaser = PaperRelease(config)
        final_pdf = releaser.release(args.input_file, args.output, dry_run=args.dry_run)

        if args.dry_run:
            print("\nSUCCESS: Dry run completed successfully")
            logger.info("Dry run completed successfully")
        else:
            print(f"\nSUCCESS: Release completed successfully!")
            print(f"Final PDF: {final_pdf}")
            logger.info(f"Release completed successfully: {final_pdf}")

        return 0

    except KeyboardInterrupt:
        print("\nWARNING: Release interrupted by user")
        logger.warning("Release interrupted by user")
        return 130
    except FileNotFoundError as e:
        print(f"\nERROR: File not found: {e}")
        logger.error(f"File not found: {e}")
        return 1
    except PermissionError as e:
        print(f"\nERROR: Permission denied: {e}")
        logger.error(f"Permission denied: {e}")
        return 1
    except ValueError as e:
        print(f"\nERROR: Invalid input or configuration: {e}")
        logger.error(f"Invalid input or configuration: {e}")
        return 1
    except subprocess.TimeoutExpired as e:
        print(f"\nERROR: Operation timed out: {e}")
        logger.error(f"Operation timed out: {e}")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: External command failed: {e}")
        logger.error(f"External command failed: {e}")
        return 1
    except Exception as e:
        print(f"\nERROR: Release failed: {e}")
        logger.exception("Release failed with unexpected exception")

        # Provide recovery suggestions
        print("\nRECOVERY SUGGESTIONS:")
        if isinstance(e, FileNotFoundError):
            print("- Check that all input files exist and paths are correct")
            print("- Ensure references.md is in the current directory")
        elif isinstance(e, PermissionError):
            print("- Check file permissions")
            print("- Ensure output directory is writable")
        elif isinstance(e, subprocess.TimeoutExpired):
            print("- Try increasing timeout in config (processing.timeout)")
            print("- Check system resources and external tool performance")
        elif "pandoc" in str(e).lower():
            print("- Verify pandoc installation: pandoc --version")
            print("- Check input file format and encoding")
        elif "typst" in str(e).lower() or "latex" in str(e).lower():
            print("- Verify typesetting tool installation")
            print("- Check for syntax errors in generated files")
        else:
            print("- Run 'python release.py --check-deps' to verify system setup")
            print("- Check release.log for detailed error information")
            print("- Try with --dry-run to isolate the issue")

        return 1

    if not args.input_file:
        parser.error("Input file is required (or use --create-config)")

    # Load configuration
    config = ReleaseConfig(args.config)

    # Override config with command-line args
    if args.format:
        config.set('format', args.format)
    if args.output:
        config.set('output.filename', Path(args.output).stem)
    if args.keep_temp:
        config.set('cleanup.temp_files', False)

    # Execute release
    releaser = PaperRelease(config)
    final_pdf = releaser.release(args.input_file, args.output)

    return 0

if __name__ == '__main__':
    exit(main())