#!/usr/bin/env python3
"""
PDF Assembler Script

This script generates PDFs from Typst/LaTeX files and allows attaching
additional documents to the front or end of the main document.

Usage:
    python pdf_assembler.py main.typ                    # Convert single file to PDF
    python pdf_assembler.py main.typ --front cover.pdf  # Add cover page
    python pdf_assembler.py main.typ --end appendix.pdf # Add appendix
    python pdf_assembler.py main.tex --output final.pdf # Custom output name
"""

import os
import re
import argparse
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

def detect_file_format(filepath):
    """Detect file format based on extension and content."""
    ext = filepath.suffix.lower()

    if ext == '.typ':
        return 'typst'
    elif ext == '.tex':
        return 'latex'
    elif ext == '.pdf':
        return 'pdf'
    else:
        # Try to detect by content
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(500)  # Read first 500 chars

            if '#set' in content or '#show' in content:
                return 'typst'
            elif '\\documentclass' in content or '\\begin{document}' in content:
                return 'latex'
            else:
                return 'unknown'
        except:
            return 'unknown'

def convert_to_pdf(input_file, output_file=None, format_type=None):
    """Convert a file to PDF based on its format."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    if format_type is None:
        format_type = detect_file_format(input_file)

    if output_file is None:
        output_file = input_file.with_suffix('.pdf')

    print(f"Converting {input_file.name} ({format_type}) to PDF...")

    if format_type == 'pdf':
        # Already a PDF, just copy if needed
        if input_file != output_file:
            import shutil
            shutil.copy2(input_file, output_file)
        return output_file

    elif format_type == 'typst':
        # Use typst compile
        cmd = ['typst', 'compile', str(input_file), str(output_file)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[OK] Typst compilation successful: {output_file}")
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Typst compilation failed: {e.stderr}")
            raise

    elif format_type == 'latex':
        # Use pdflatex
        # Change to the file's directory for proper relative path handling
        original_dir = os.getcwd()
        try:
            os.chdir(input_file.parent)
            cmd = ['pdflatex', '-interaction=nonstopmode', input_file.name]

            # Run pdflatex (may need multiple passes for references)
            for i in range(2):  # Run twice to resolve references
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    if i == 0:
                        print(f"Warning: First pdflatex pass had issues: {result.stderr}")
                    else:
                        print(f"[ERROR] pdflatex compilation failed: {result.stderr}")
                        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

            # Check if PDF was created
            pdf_file = input_file.with_suffix('.pdf')
            if pdf_file.exists():
                if output_file != pdf_file:
                    import shutil
                    shutil.copy2(pdf_file, output_file)
                print(f"[OK] LaTeX compilation successful: {output_file}")
                return output_file
            else:
                raise FileNotFoundError(f"pdflatex did not generate PDF file")

        finally:
            os.chdir(original_dir)

    else:
        raise ValueError(f"Unsupported format: {format_type}")

def merge_pdfs(pdf_files, output_file):
    """Merge multiple PDF files into one."""
    if len(pdf_files) == 1:
        # Just copy the single file
        import shutil
        shutil.copy2(pdf_files[0], output_file)
        return output_file

    # Try using Python's pypdf if available
    try:
        from pypdf import PdfMerger
        merger = PdfMerger()

        for pdf in pdf_files:
            merger.append(str(pdf))

        merger.write(str(output_file))
        merger.close()
        print(f"[OK] PDFs merged successfully: {output_file}")
        return output_file

    except ImportError:
        print("pypdf not available. Trying alternative methods...")

        # Try using pdftk if available
        try:
            cmd = ['pdftk'] + [str(f) for f in pdf_files] + ['cat', 'output', str(output_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[OK] PDFs merged with pdftk: {output_file}")
            return output_file
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Try using pdfunite if available
        try:
            cmd = ['pdfunite'] + [str(f) for f in pdf_files] + [str(output_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"[OK] PDFs merged with pdfunite: {output_file}")
            return output_file
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # As a last resort, provide instructions for manual merging
        print("WARNING: No PDF merging tools available. Please merge manually:")
        print(f"Input files: {', '.join(str(f) for f in pdf_files)}")
        print(f"Output file: {output_file}")
        print("\nManual merging options:")
        print("1. Use online PDF merger tools")
        print("2. Install pypdf: pip install pypdf")
        print("3. Install pdftk or pdfunite")
        raise RuntimeError("No PDF merging tools available")

def main():
    parser = argparse.ArgumentParser(
        description='Generate PDFs from Typst/LaTeX files and attach additional documents.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_assembler.py paper.typ                          # Convert to PDF
  python pdf_assembler.py paper.typ --front cover.pdf        # Add cover
  python pdf_assembler.py paper.typ --end appendix.pdf       # Add appendix
  python pdf_assembler.py paper.tex --output final.pdf       # Custom output
  python pdf_assembler.py main.typ --front title.pdf --end refs.pdf --output complete.pdf
        """
    )

    parser.add_argument('main_file', help='Main document file (.typ, .tex, or .pdf)')
    parser.add_argument('--front', nargs='+', help='Files to attach to the front (PDF, Typst, or LaTeX)')
    parser.add_argument('--end', nargs='+', help='Files to attach to the end (PDF, Typst, or LaTeX)')
    parser.add_argument('--output', '-o', help='Output PDF filename (default: based on main file)')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary PDF files')

    args = parser.parse_args()

    # Convert main file path
    main_file = Path(args.main_file)
    if not main_file.exists():
        print(f"Error: Main file '{main_file}' does not exist")
        return 1

    # Set default output name
    if not args.output:
        args.output = main_file.with_suffix('.pdf').name

    output_file = Path(args.output)

    print(f"PDF Assembler - Processing {main_file.name}")
    print(f"Output: {output_file}")
    print("-" * 50)

    # Collect all files to process
    files_to_process = []

    # Add front files
    if args.front:
        for f in args.front:
            files_to_process.append(('front', Path(f)))

    # Add main file
    files_to_process.append(('main', main_file))

    # Add end files
    if args.end:
        for f in args.end:
            files_to_process.append(('end', Path(f)))

    # Convert all files to PDFs
    pdf_files = []
    temp_files = []

    try:
        for position, input_file in files_to_process:
            print(f"\nProcessing {position} file: {input_file.name}")

            # Create temporary PDF for non-PDF files
            if detect_file_format(input_file) != 'pdf':
                temp_pdf = input_file.with_suffix('.pdf')
                convert_to_pdf(input_file, temp_pdf)
                pdf_files.append(temp_pdf)
                if not args.keep_temp:
                    temp_files.append(temp_pdf)
            else:
                pdf_files.append(input_file)

        # Merge all PDFs
        if len(pdf_files) > 1:
            print(f"\nMerging {len(pdf_files)} PDF files...")
            merge_pdfs(pdf_files, output_file)
        else:
            # Single file, just ensure it's named correctly
            if pdf_files[0] != output_file:
                import shutil
                shutil.copy2(pdf_files[0], output_file)
            print(f"[OK] Single PDF file ready: {output_file}")

        print(f"\nSUCCESS! Final PDF: {output_file}")
        print(f"   Total pages from {len(pdf_files)} source(s)")

        # Clean up temporary files
        if not args.keep_temp:
            for temp_file in temp_files:
                try:
                    if temp_file.exists() and temp_file != output_file:
                        temp_file.unlink()
                        print(f"[CLEANUP] Removed temporary file: {temp_file.name}")
                except OSError:
                    pass

    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())