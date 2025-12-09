#!/usr/bin/env python3
"""
References Organizer Script

This script alphabetizes and deduplicates references in references.md format.
It preserves the exact formatting while ensuring proper ordering and uniqueness.

Usage:
    python references_organizer.py                    # Process references.md
    python references_organizer.py --file custom.md   # Process custom file
    python references_organizer.py --dry-run          # Show changes without writing
    python references_organizer.py --backup           # Create backup before processing
"""

import os
import re
import argparse
from pathlib import Path
from datetime import datetime


def parse_reference_block(block):
    """Parse a reference block to extract sorting key and content."""
    lines = block.strip().split('\n')
    if not lines:
        return None, None

    first_line = lines[0].strip()

    # Skip headers and comments
    if first_line.startswith('#') or first_line.startswith('<!--'):
        return None, None

    # Extract author and year for sorting
    # Pattern: "Author. Year." or "Author1, Author2. Year." etc.
    match = re.match(r'^(.+?)\s+(\d{4}|Forthcoming)\.', first_line)
    if match:
        author_part = match.group(1).strip()
        year_part = match.group(2)

        # Create sorting key: normalize author name for consistent sorting
        # Remove extra spaces, handle "and" vs "&", etc.
        sort_key = re.sub(r'\s+', ' ', author_part.lower())
        sort_key = re.sub(r'\band\b', '&', sort_key)  # Normalize "and" to "&"
        sort_key = re.sub(r'[,&]', '', sort_key)  # Remove separators for sorting

        return f"{sort_key}_{year_part}", block.strip()
    else:
        # Not a valid reference block
        return None, None


def load_references(filepath):
    """Load references from file and split into blocks."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    # Split by double newlines (reference blocks are separated by blank lines)
    blocks = re.split(r'\n\s*\n', content)

    references = []
    for block in blocks:
        if block.strip():  # Skip empty blocks
            result = parse_reference_block(block)
            if result[0] is not None:  # Valid reference block
                references.append(result)

    return references


def deduplicate_references(references):
    """Remove duplicate references, keeping the first occurrence."""
    seen = set()
    deduplicated = []

    for sort_key, content in references:
        # Use content hash for deduplication
        content_hash = hash(content)
        if content_hash not in seen:
            seen.add(content_hash)
            deduplicated.append((sort_key, content))

    return deduplicated


def save_references(filepath, references, backup=False):
    """Save organized references to file."""
    if backup:
        backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(filepath, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # Add header
            f.write("# References\n\n")
            f.write(f"<!-- Organized on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n\n")

            # Write references
            for i, (_, content) in enumerate(references):
                f.write(f"{content}\n\n")

        print(f"Successfully organized {len(references)} references in {filepath}")

    except Exception as e:
        print(f"Error writing {filepath}: {e}")
        return False

    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Alphabetize and deduplicate references in markdown format.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python references_organizer.py                    # Process references.md
  python references_organizer.py --file custom.md   # Process custom file
  python references_organizer.py --dry-run          # Show changes without writing
  python references_organizer.py --backup           # Create backup before processing
        """
    )

    parser.add_argument('--file', '-f', default='references.md',
                       help='References file to process (default: references.md)')
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help='Show changes without writing to file')
    parser.add_argument('--backup', '-b', action='store_true',
                       help='Create backup before processing')

    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File {filepath} does not exist")
        return 1

    print(f"Processing {filepath}...")

    # Load references
    references = load_references(filepath)
    if not references:
        print("No references found")
        return 1

    print(f"Loaded {len(references)} reference blocks")

    # Sort alphabetically
    references.sort(key=lambda x: x[0])
    print("Sorted references alphabetically")

    # Deduplicate
    original_count = len(references)
    references = deduplicate_references(references)
    if len(references) < original_count:
        print(f"Removed {original_count - len(references)} duplicate references")

    # Show summary
    print(f"\nSummary:")
    print(f"  Total references: {len(references)}")
    print(f"  First reference: {references[0][1].split('.')[0] if references else 'None'}")
    print(f"  Last reference: {references[-1][1].split('.')[0] if references else 'None'}")

    if args.dry_run:
        print("\nDry run - no changes written")
        return 0

    # Save
    if save_references(filepath, references, backup=args.backup):
        print("Processing complete!")
        return 0
    else:
        return 1


if __name__ == '__main__':
    exit(main())