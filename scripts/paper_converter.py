#!/usr/bin/env python3
"""
Paper Converter Script

This script processes a markdown paper file by:
1. Extracting citations
2. Generating a filtered references file with only cited references
3. Combining the paper with references
4. Converting to LaTeX or Typst using pandoc

Usage:
    python paper_converter.py paper.md                    # Convert to LaTeX
    python paper_converter.py paper.md --format typst    # Convert to Typst
    python paper_converter.py paper.md --preamble preamble.tex  # Use custom preamble
    python paper_converter.py paper.md --output final.tex # Custom output file
"""

import os
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Import citation extraction functions from citation_extractor module
try:
    import citation_extractor
    CITATION_EXTRACTOR_AVAILABLE = True
except ImportError:
    CITATION_EXTRACTOR_AVAILABLE = False
    print("Warning: citation_extractor module not found, using fallback extraction")

def is_valid_citation(author, year):
    """Check if a potential citation is valid (not an abbreviation or invalid format)."""
    # Skip if author contains common abbreviations
    invalid_words = ['cf.', 'e.g.', 'i.e.', 'cf', 'eg', 'ie', 'vs.', 'vs', 'etc.', 'etc', 'et al.', 'et al', 'originally']
    if any(word in author.lower() for word in invalid_words):
        return False

    # Skip if year is not a digit or 'Forthcoming'
    if not (year.isdigit() or year == 'Forthcoming'):
        return False

    return True

def extract_citations_from_file(filepath):
    """Extract both parenthetical and in-prose citations from a file."""
    # Use the updated citation_extractor module if available
    if CITATION_EXTRACTOR_AVAILABLE:
        return citation_extractor.extract_citations_from_file(Path(filepath), verbose=False)

    # Fallback to basic extraction if module not available
    citations = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return citations

    lines = content.split('\n')

    # Pattern 1: Parenthetical citations
    parenthetical_pattern = r'\(([^)]*?\d{4}[^)]*?)\)'

    # Pattern 2: In-prose citations
    in_prose_pattern = r'\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?(?:\'s)?(?:\s+(?:and|&)\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)?(?:\s+et\s+al\.?)?)\s+\(([A-Za-z]+|\d{4})(?:[a-z])?\)'

    for i, line in enumerate(lines):
        # Find parenthetical citations
        for match in re.finditer(parenthetical_pattern, line):
            citation_content = match.group(1)
            all_parts = []
            semicolon_parts = [part.strip() for part in citation_content.split(';')]
            for semicolon_part in semicolon_parts:
                comma_parts = [part.strip() for part in semicolon_part.split(',')]
                all_parts.extend(comma_parts)

            for part in all_parts:
                part_match = re.match(r'^(.+?)\s+(\d{4}[a-z]?)$', part.strip())
                if part_match:
                    author = part_match.group(1).strip()
                    year = part_match.group(2)

                    if not is_valid_citation(author, year):
                        continue

                    citations.append({
                        'citation': f"({author} {year})",
                        'author': author,
                        'year': year,
                        'type': 'parenthetical',
                        'line': i + 1
                    })

        # Find in-prose citations
        for match in re.finditer(in_prose_pattern, line):
            full_match = match.group(0)
            author = match.group(1).strip()
            year = match.group(2)

            # Strip possessive 's from author name
            if author.endswith("'s"):
                author = author[:-2]

            if not is_valid_citation(author, year):
                continue

            if i > 0 and re.match(r'^[A-Z][a-z]+.*\d{4}\.', line):
                continue

            citations.append({
                'citation': full_match,
                'author': author,
                'year': year,
                'type': 'in-prose',
                'line': i + 1
            })

    return citations

def load_references():
    """Load references from references.md into a dictionary."""
    # Use the updated citation_extractor module if available
    if CITATION_EXTRACTOR_AVAILABLE:
        return citation_extractor.load_references()

    # Fallback implementation
    references = {}

    try:
        with open('references.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading references.md: {e}")
        return references

    # Split into individual references
    ref_blocks = re.split(r'\n\n(?=[A-Z])', content)

    for block in ref_blocks:
        if not block.strip() or block.startswith('#'):
            continue

        lines = block.strip().split('\n')
        if not lines:
            continue

        first_line = lines[0].strip()

        # Match pattern like "Author. Year." or "Author1, Author2. Year." or "Author. Forthcoming."
        match = re.search(r'^(.+?)\s+(\d{4}|[A-Z][a-z]+)\.', first_line)
        if match:
            full_author = match.group(1).strip()
            year = match.group(2)

            # Extract primary author (last name before first comma)
            primary_author = full_author.split(',')[0].strip()

            # Handle "Author1, Author2" format
            if ',' in full_author:
                parts = full_author.split(',')
                if len(parts) >= 2:
                    second_part = parts[1].strip()
                    if ' and ' in second_part or ' & ' in second_part:
                        pass
                    elif not re.match(r'^[A-Z]\.\s*[A-Z]\.?', second_part):
                        second_author = second_part.split()[0] if second_part else ''
                        if second_author:
                            key_and = f"{primary_author} and {second_author}"
                            references[key_and] = block.strip()
                            references[f"{key_and} {year}"] = block.strip()

            # Store multiple possible keys
            references[primary_author] = block.strip()
            references[f"{primary_author} {year}"] = block.strip()
            references[full_author] = block.strip()
            references[f"{full_author} {year}"] = block.strip()

            # Handle "et al." citations
            references[f"{primary_author} et al"] = block.strip()
            references[f"{primary_author} et al. {year}"] = block.strip()

    return references

def match_citation_to_reference(author, year, references, config=None):
    """Try multiple strategies to match a citation to a reference with configurable options."""
    # Use the updated citation_extractor module if available (it doesn't use config)
    if CITATION_EXTRACTOR_AVAILABLE:
        return citation_extractor.match_citation_to_reference(author, year, references)

    # Fallback implementation with config support
    if config is None:
        config = {
            'strict_matching': True,
            'case_sensitive': False,
            'fuzzy_matching': True
        }

    # Normalize author based on config
    normalized_author = author if config.get('case_sensitive', False) else author.lower()
    normalized_references = references if config.get('case_sensitive', False) else {k.lower(): v for k, v in references.items()}

    # Try exact matches first
    possible_keys = [
        f"{normalized_author} {year}",
        normalized_author,
        f"{normalized_author.replace(' and ', ', ')} {year}",
        f"{normalized_author.replace(' & ', ', ')} {year}",
    ]

    # Handle "et al." by stripping it and trying primary author
    if 'et al' in normalized_author.lower():
        primary = normalized_author.split('et al')[0].strip()
        possible_keys.extend([
            f"{primary} et al. {year}",
            f"{primary} et al {year}",
            f"{primary} {year}",
            primary
        ])

    # Handle "Author1 and Author2" by trying primary author
    if ' and ' in normalized_author or ' & ' in normalized_author:
        primary = normalized_author.split(' and ')[0].split(' & ')[0].strip()
        possible_keys.extend([
            f"{primary} {year}",
            primary
        ])

    # Try exact matches
    for key in possible_keys:
        if key in normalized_references:
            return references.get(key if config.get('case_sensitive', False) else next((k for k in references.keys() if k.lower() == key), None))

    # If strict matching is disabled, try fuzzy matching
    if not config.get('strict_matching', True) and config.get('fuzzy_matching', True):
        return fuzzy_match_citation(normalized_author, year, references, config)

    return None

def fuzzy_match_citation(author, year, references, config):
    """Perform fuzzy matching for citations when exact match fails."""
    # Try partial author matches
    author_parts = author.split()
    if author_parts:
        primary_author = author_parts[0]

        # Try with just the primary author
        for ref_key, ref_value in references.items():
            normalized_key = ref_key.lower() if not config.get('case_sensitive', False) else ref_key
            if primary_author.lower() in normalized_key and str(year) in normalized_key:
                return ref_value

        # Try with first few letters of primary author
        if len(primary_author) >= 3:
            prefix = primary_author[:3].lower()
            for ref_key, ref_value in references.items():
                normalized_key = ref_key.lower() if not config.get('case_sensitive', False) else ref_key
                if normalized_key.startswith(prefix) and str(year) in normalized_key:
                    return ref_value

    return None

def generate_filtered_references(citations, references, output_file, strategy='filter', config=None):
    """Generate a references file based on the specified strategy."""
    if config is None:
        config = {
            'strict_matching': True,
            'case_sensitive': False,
            'fuzzy_matching': True,
            'include_missing': False
        }

    if strategy == 'filter':
        return generate_filtered_references_only(citations, references, output_file, config)
    elif strategy == 'merge':
        return generate_merged_references(citations, references, output_file, config)
    elif strategy == 'keep':
        return generate_keep_references(citations, references, output_file, config)
    else:
        raise ValueError(f"Unknown reference strategy: {strategy}")

def generate_filtered_references_only(citations, references, output_file, config):
    """Generate a filtered references file containing only cited references."""
    # Collect unique references
    unique_refs = {}
    missing_refs = []

    for citation in citations:
        ref = match_citation_to_reference(citation['author'], citation['year'], references, config)
        if ref:
            # Use the first line as a key to avoid duplicates
            first_line = ref.split('\n')[0].strip()
            if first_line not in unique_refs:
                unique_refs[first_line] = ref
        else:
            missing_refs.append(f"{citation['author']} ({citation['year']})")

    # Sort references alphabetically by primary author
    sorted_refs = sorted(unique_refs.values(), key=lambda x: x.split('.')[0].strip().lower())

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("## References\n\n")
        f.write(f"<!-- Generated for paper conversion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n")
        f.write(f"<!-- Strategy: filter (cited references only) -->\n")
        f.write(f"<!-- Total references: {len(sorted_refs)} -->\n\n")

        for ref in sorted_refs:
            f.write(f"{ref}\n\n")

        if missing_refs and config.get('include_missing', False):
            f.write("\n<!-- MISSING REFERENCES (Not found in references.md) -->\n")
            for missing in sorted(set(missing_refs)):
                f.write(f"<!-- {missing} -->\n")

    return len(sorted_refs), len(set(missing_refs))

def generate_merged_references(citations, references, output_file, config):
    """Generate a references file containing all references, with cited ones marked."""
    # Get unique references from references.md (deduplicate since dict has multiple keys per reference)
    all_refs = list(set(references.values()))

    # Mark which references are cited
    cited_refs = set()
    missing_refs = []

    for citation in citations:
        ref = match_citation_to_reference(citation['author'], citation['year'], references, config)
        if ref:
            # Use the first line as a key to identify cited references
            first_line = ref.split('\n')[0].strip()
            cited_refs.add(first_line)
        else:
            missing_refs.append(f"{citation['author']} ({citation['year']})")

    # Sort references alphabetically by primary author
    sorted_refs = sorted(all_refs, key=lambda x: x.split('.')[0].strip().lower())

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("## References\n\n")
        f.write(f"<!-- Generated for paper conversion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n")
        f.write(f"<!-- Strategy: merge (all references) -->\n")
        f.write(f"<!-- Total references: {len(sorted_refs)}, Cited: {len(cited_refs)} -->\n\n")

        for ref in sorted_refs:
            first_line = ref.split('\n')[0].strip()
            if first_line in cited_refs:
                f.write(f"{ref} <!-- CITED -->\n\n")
            else:
                f.write(f"{ref}\n\n")

        if missing_refs and config.get('include_missing', False):
            f.write("\n<!-- MISSING REFERENCES (Not found in references.md) -->\n")
            for missing in sorted(set(missing_refs)):
                f.write(f"<!-- {missing} -->\n")

    return len(sorted_refs), len(set(missing_refs))

def generate_keep_references(citations, references, output_file, config):
    """Generate a references file by keeping existing references section unchanged."""
    # For 'keep' strategy, we just copy the original references.md
    # But we still validate citations and report missing ones
    missing_refs = []

    for citation in citations:
        ref = match_citation_to_reference(citation['author'], citation['year'], references, config)
        if not ref:
            missing_refs.append(f"{citation['author']} ({citation['year']})")

    # Copy references.md to output file
    try:
        with open('references.md', 'r', encoding='utf-8') as f:
            refs_content = f.read()
    except Exception as e:
        raise RuntimeError(f"Could not read references.md: {e}")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("## References\n\n")
        f.write(f"<!-- Generated for paper conversion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n")
        f.write(f"<!-- Strategy: keep (existing references section) -->\n")
        f.write(f"<!-- Total references: {len(references)} -->\n\n")
        f.write(refs_content)

        if missing_refs and config.get('include_missing', False):
            f.write("\n<!-- MISSING REFERENCES (Not found in references.md) -->\n")
            for missing in sorted(set(missing_refs)):
                f.write(f"<!-- {missing} -->\n")

    return len(references), len(set(missing_refs))

def remove_references_section(content):
    """Remove any existing references section from the content."""
    # Look for references section (case insensitive)
    lines = content.split('\n')
    new_lines = []
    in_references = False
    skip_until_next_header = False

    for i, line in enumerate(lines):
        # Check if this is the start of a references section
        if re.match(r'^#+\s*references', line, re.IGNORECASE):
            in_references = True
            skip_until_next_header = True
            continue

        # If we're in references section, skip lines
        if in_references:
            # Check if we've reached the next major section (another # header)
            if re.match(r'^#\s+', line) and not skip_until_next_header:
                in_references = False
            elif skip_until_next_header:
                # Skip this line as it's part of references
                continue
            else:
                # This shouldn't happen, but skip anyway
                continue

        new_lines.append(line)

    return '\n'.join(new_lines)

def combine_paper_and_references(paper_file, filtered_refs_file, output_file):
    """Combine the paper content with filtered references."""
    # Read paper content
    with open(paper_file, 'r', encoding='utf-8') as f:
        paper_content = f.read()

    # Remove existing references section
    paper_content = remove_references_section(paper_content)

    # Read filtered references
    with open(filtered_refs_file, 'r', encoding='utf-8') as f:
        refs_content = f.read()

    # Combine
    combined_content = paper_content.rstrip() + '\n\n' + refs_content

    # Write combined file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(combined_content)

    return output_file

def convert_with_pandoc(input_file, output_file, format_type, preamble_file=None):
    """Convert markdown to LaTeX or Typst using pandoc."""
    cmd = ['pandoc', input_file]

    if format_type.lower() == 'latex':
        cmd.extend(['--pdf-engine=pdflatex', '-o', output_file])
        if preamble_file:
            cmd.extend(['--include-in-header', preamble_file])
    elif format_type.lower() == 'typst':
        # For Typst, convert to a temporary file first, then prepend preamble
        temp_output = output_file + '.tmp'
        cmd.extend(['--to', 'typst', '-o', temp_output])
    else:
        raise ValueError(f"Unsupported format: {format_type}")

    # For markdown with embedded references, we don't need citeproc
    # The references are already in the document

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Handle Typst preamble by prepending it to the output
        if format_type.lower() == 'typst':
            temp_output = output_file + '.tmp'
            with open(temp_output, 'r', encoding='utf-8') as f:
                typst_content = f.read()

            final_content = ""
            if preamble_file:
                try:
                    with open(preamble_file, 'r', encoding='utf-8') as f:
                        preamble_content = f.read()
                    final_content = preamble_content + '\n\n' + typst_content
                except Exception as e:
                    print(f"Warning: Could not read preamble file {preamble_file}: {e}")
                    final_content = typst_content
            else:
                final_content = typst_content

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_content)

            # Clean up temp file
            try:
                os.remove(temp_output)
            except OSError:
                pass

        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown paper to LaTeX or Typst with configurable reference handling.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python paper_converter.py paper.md                           # Convert to LaTeX (filter strategy)
  python paper_converter.py paper.md --format typst           # Convert to Typst
  python paper_converter.py paper.md --strategy merge         # Include all references
  python paper_converter.py paper.md --strategy keep          # Keep existing references
  python paper_converter.py paper.md --preamble preamble.tex  # Use custom preamble
  python paper_converter.py paper.md --output final.tex       # Custom output file
  python paper_converter.py paper.md --keep-temp              # Keep temporary files
        """
    )

    parser.add_argument('input_file', help='Input markdown file')
    parser.add_argument('--format', choices=['latex', 'typst'], default='latex',
                        help='Output format (default: latex)')
    parser.add_argument('--output', '-o', help='Output file name (default: based on input)')
    parser.add_argument('--preamble', help='Preamble file to include (LaTeX only)')
    parser.add_argument('--strategy', choices=['filter', 'merge', 'keep'], default='filter',
                        help='Reference handling strategy: filter (cited only), merge (all), keep (existing)')
    parser.add_argument('--strict-matching', action='store_true', default=True,
                        help='Require exact matches for citations')
    parser.add_argument('--no-strict-matching', action='store_false', dest='strict_matching',
                        help='Allow fuzzy matching for citations')
    parser.add_argument('--case-sensitive', action='store_true', default=False,
                        help='Case sensitive author matching')
    parser.add_argument('--include-missing', action='store_true', default=False,
                        help='Include missing citations as comments')
    parser.add_argument('--keep-temp', action='store_true',
                        help='Keep temporary files (combined markdown)')

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' does not exist")
        return 1

    # Set default output file
    if not args.output:
        if args.format == 'latex':
            args.output = input_path.stem + '.tex'
        else:  # typst
            args.output = input_path.stem + '.typ'

    # Check for references.md
    if not Path('references.md').exists():
        print("Error: references.md not found in current directory")
        return 1

    print(f"Processing {args.input_file}...")

    # Step 1: Extract citations
    print("Extracting citations...")
    citations = extract_citations_from_file(input_path)
    print(f"Found {len(citations)} citations")

    # Step 2: Load references
    print("Loading references...")
    references = load_references()
    print(f"Loaded {len(references)} reference entries")

    # Create config for citation matching
    citation_config = {
        'strict_matching': args.strict_matching,
        'case_sensitive': args.case_sensitive,
        'fuzzy_matching': True,  # Always enable fuzzy matching for now
        'include_missing': args.include_missing
    }

    # Step 3: Generate references based on strategy
    filtered_refs_file = f"{input_path.stem}_refs_filtered.md"
    print(f"Generating references (strategy: {args.strategy})...")
    num_refs, num_missing = generate_filtered_references(citations, references, filtered_refs_file, args.strategy, citation_config)
    print(f"Generated {num_refs} references")
    if num_missing > 0:
        print(f"Warning: {num_missing} citations not found in references.md")

    # Step 4: Combine paper and references
    combined_file = f"{input_path.stem}_combined.md"
    print("Combining paper with references...")
    combine_paper_and_references(args.input_file, filtered_refs_file, combined_file)

    # Step 5: Convert with pandoc
    print(f"Converting to {args.format}...")
    success, output = convert_with_pandoc(
        combined_file,
        args.output,
        args.format,
        args.preamble
    )

    if success:
        print(f"Success! Output written to {args.output}")
    else:
        print(f"Error during conversion: {output}")
        return 1

    # Clean up temporary files unless requested to keep them
    if not args.keep_temp:
        try:
            os.remove(filtered_refs_file)
            os.remove(combined_file)
            print("Temporary files cleaned up")
        except OSError:
            pass

    return 0

if __name__ == '__main__':
    exit(main())