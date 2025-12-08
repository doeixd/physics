#!/usr/bin/env python3
"""
Enhanced Citation Extractor Script

This script scans markdown files for both parenthetical and in-prose citations,
extracts their context, and looks up corresponding references.

Usage:
    python citation_extractor.py                    # Scan all .md files
    python citation_extractor.py final.md          # Scan specific file
    python citation_extractor.py -o output.txt     # Custom output file
    python citation_extractor.py final.md -o citations.txt
"""

import os
import re
import argparse
from pathlib import Path
from datetime import datetime

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

def extract_citations_from_file(filepath, verbose=True):
    """Extract both parenthetical and in-prose citations from a file."""
    citations = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        if verbose:
            print(f"Error reading {filepath}: {e}")
        return citations

    lines = content.split('\n')

    # Pattern 1: Parenthetical citations - find all text within parentheses that contains years
    parenthetical_pattern = r'\(([^)]*?\d{4}[^)]*?)\)'

    # Pattern 2: Possessive citations like "Author's (Year)" or "Author1 and Author2's (Year)"
    # Matches: Davidson's (1986), Kitcher's (1993), Longino's (1990), Ladyman and Ross's (2007), O'Connor's (2019)
    # IMPORTANT: Check possessive BEFORE in-prose to avoid in-prose matching "Davidson's" as "Davidson's"
    # Pattern uses [\w']* to allow internal apostrophes (O'Connor) but must end with \w to avoid capturing trailing apostrophe
    possessive_pattern = r'\b([A-Z][\w\']*\w(?:\s+(?:and|&)\s+[A-Z][\w\']*\w)?)\'s\s+\((\d{4})(?:[a-z])?\)'

    # Pattern 3: In-prose citations like "Author (Year)" or "Author et al. (Year)"
    # Matches: Goldman (1979), Quine (1951), Acemoglu and Robinson (2012),
    #          Sevilla et al. (2022), Bennett-Hunter (2015), O'Connor (2019)
    # Updated to handle apostrophes in names like O'Connor, O'Neill, etc.
    in_prose_pattern = r'\b([A-Z][\w\']+(?:-[A-Z][\w\']+)?(?:\s+(?:and|&)\s+[A-Z][\w\']+(?:-[A-Z][\w\']+)?)?(?:\s+et\s+al\.?)?)\s+\((\d{4})(?:[a-z])?\)'

    # Track which citations have already been found to avoid duplicates
    # Use (line_number, start_position) as key
    found_citations = set()

    for i, line in enumerate(lines):
        # Find parenthetical citations
        for match in re.finditer(parenthetical_pattern, line):
            citation = match.group(0)
            citation_content = match.group(1)

            # Extract context once
            start_line = max(0, i - 3)
            end_line = min(len(lines), i + 4)
            context = '\n'.join(lines[start_line:end_line]).strip()

            # Parse the citation to extract all author-year pairs
            # Handle both semicolon-separated and comma-separated citations
            # First split by semicolons, then by commas for each part
            all_parts = []
            semicolon_parts = [part.strip() for part in citation_content.split(';')]
            for semicolon_part in semicolon_parts:
                comma_parts = [part.strip() for part in semicolon_part.split(',')]
                all_parts.extend(comma_parts)

            for part in all_parts:
                # Try to extract author and year from each part
                # Pattern: "Author Year" or "Author et al. Year" or "Author1 and Author2 Year"
                part_match = re.match(r'^(.+?)\s+(\d{4}[a-z]?)$', part.strip())
                if part_match:
                    author = part_match.group(1).strip()
                    year = part_match.group(2)

                    # Skip invalid citations
                    if not is_valid_citation(author, year):
                        continue

                    citations.append({
                        'citation': f"({author} {year})",
                        'author': author,
                        'year': year,
                        'type': 'parenthetical',
                        'context': context,
                        'file': filepath.name,
                        'line': i + 1
                    })

        # Find possessive citations FIRST (before in-prose) to avoid conflicts
        for match in re.finditer(possessive_pattern, line):
            full_match = match.group(0)
            author = match.group(1).strip()
            year = match.group(2)

            # Track this citation location
            cite_key = (i, match.start())
            if cite_key in found_citations:
                continue
            found_citations.add(cite_key)

            # Extract context
            start_line = max(0, i - 3)
            end_line = min(len(lines), i + 4)
            context = '\n'.join(lines[start_line:end_line]).strip()

            citations.append({
                'citation': full_match,
                'author': author,
                'year': year,
                'type': 'possessive',
                'context': context,
                'file': filepath.name,
                'line': i + 1
            })

        # Find in-prose citations (after possessive to avoid conflicts)
        for match in re.finditer(in_prose_pattern, line):
            # Get the full match including author name before parentheses
            full_match = match.group(0)
            author = match.group(1).strip()
            year = match.group(2)

            # Skip if already found as possessive
            cite_key = (i, match.start())
            if cite_key in found_citations:
                continue
            found_citations.add(cite_key)

            # Skip if this looks like it's part of a reference list entry
            # (reference entries have author at start of line followed by year)
            if i > 0 and re.match(r'^[A-Z][a-z]+.*\d{4}\.', line):
                continue

            # Extract context
            start_line = max(0, i - 3)
            end_line = min(len(lines), i + 4)
            context = '\n'.join(lines[start_line:end_line]).strip()

            citations.append({
                'citation': full_match,
                'author': author,
                'year': year,
                'type': 'in-prose',
                'context': context,
                'file': filepath.name,
                'line': i + 1
            })

    return citations

def load_references():
    """Load references from references.md into a dictionary."""
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
        # Use greedy match for author, then capture year (4 digits or "Forthcoming")
        match = re.search(r'^(.+)\s+(\d{4}|Forthcoming)\.', first_line)
        if match:
            full_author = match.group(1).strip()
            year = match.group(2)

            # Extract primary author (last name before first comma)
            primary_author = full_author.split(',')[0].strip()
            # Strip trailing dots from institutional authors
            primary_author = primary_author.rstrip('.')
            full_author = full_author.rstrip('.')

            # Check for "originally" year in the block
            original_year = None
            for line in lines:
                orig_match = re.search(r'\(originally (\d{4})\)', line)
                if orig_match:
                    original_year = orig_match.group(1)
                    break

            # Handle "Author1, Author2" format
            # Also handle "Author et al." format
            # Check if there's an "and" or "&" indicating multiple authors
            # Format can be: "Author1, FirstName, and Author2, FirstName" or "Author1, FirstName and Author2, FirstName"
            if ',' in full_author and (' and ' in full_author or ' & ' in full_author):
                # Extract second author from "and" or "&" clause
                and_part = None
                if ' and ' in full_author:
                    and_part = full_author.split(' and ')[-1].strip()
                elif ' & ' in full_author:
                    and_part = full_author.split(' & ')[-1].strip()

                if and_part:
                    # Get the last name from "FirstName LastName" or just "LastName"
                    # Handle formats like "James Owen Weatherall" -> "Weatherall"
                    second_author = and_part.split(',')[0].strip()  # Remove any trailing commas
                    second_author = second_author.rstrip('.')  # Remove trailing period
                    # Get last word as the last name
                    second_author_lastname = second_author.split()[-1] if second_author.split() else second_author

                    if second_author_lastname:
                        # Store as both "Author1 and Author2" and "Author1 & Author2"
                        key_and = f"{primary_author} and {second_author_lastname}"
                        key_ampersand = f"{primary_author} & {second_author_lastname}"
                        references[key_and] = block.strip()
                        references[key_ampersand] = block.strip()
                        references[f"{key_and} {year}"] = block.strip()
                        references[f"{key_ampersand} {year}"] = block.strip()
                        if original_year:
                            references[f"{key_and} {original_year}"] = block.strip()
                            references[f"{key_ampersand} {original_year}"] = block.strip()
            elif ',' in full_author:
                # Old logic for simple two-author format without "and"
                parts = full_author.split(',')
                if len(parts) >= 2:
                    second_part = parts[1].strip()
                    if not re.match(r'^[A-Z]\.\s*[A-Z]\.?', second_part):
                        # Second author exists (not just initials)
                        second_author = second_part.split()[0] if second_part else ''
                        if second_author:
                            # Store as both "Author1 and Author2" and "Author1 & Author2"
                            key_and = f"{primary_author} and {second_author}"
                            key_ampersand = f"{primary_author} & {second_author}"
                            references[key_and] = block.strip()
                            references[key_ampersand] = block.strip()
                            references[f"{key_and} {year}"] = block.strip()
                            references[f"{key_ampersand} {year}"] = block.strip()
                            if original_year:
                                references[f"{key_and} {original_year}"] = block.strip()
                                references[f"{key_ampersand} {original_year}"] = block.strip()

            # Store multiple possible keys
            references[primary_author] = block.strip()
            references[f"{primary_author} {year}"] = block.strip()
            references[full_author] = block.strip()
            references[f"{full_author} {year}"] = block.strip()

            # Store with original year if available
            if original_year:
                references[f"{primary_author} {original_year}"] = block.strip()
                references[f"{full_author} {original_year}"] = block.strip()

    return references

def match_citation_to_reference(author, year, references):
    """Try multiple strategies to match a citation to a reference."""
    # Try exact matches first
    possible_keys = [
        f"{author} {year}",
        author,
        f"{author.replace(' and ', ', ')} {year}",
        f"{author.replace(' & ', ', ')} {year}",
        # Also try replacing "&" with "and" and vice versa
        f"{author.replace(' and ', ' & ')} {year}",
        f"{author.replace(' & ', ' and ')} {year}",
        author.replace(' and ', ' & '),
        author.replace(' & ', ' and '),
    ]

    # Handle "et al." by stripping it and trying primary author
    if 'et al' in author.lower():
        primary = author.split('et al')[0].strip()
        possible_keys.extend([
            f"{primary} et al. {year}",
            f"{primary} et al {year}",
            f"{primary} {year}",
            primary
        ])

    # Handle "Author1 and Author2" by trying primary author
    if ' and ' in author or ' & ' in author:
        primary = author.split(' and ')[0].split(' & ')[0].strip()
        possible_keys.extend([
            f"{primary} {year}",
            primary
        ])

    for key in possible_keys:
        if key in references:
            return references[key]

    return None

def generate_references_file(citations, references, output_file, paper_files, quiet=False):
    """Generate a new references.md file containing only cited references."""
    # Collect unique references
    unique_refs = {}
    missing_refs = []

    for citation in citations:
        ref = match_citation_to_reference(citation['author'], citation['year'], references)
        if ref:
            # Use the first line as a key to avoid duplicates
            first_line = ref.split('\n')[0].strip()
            if first_line not in unique_refs:
                unique_refs[first_line] = ref
        else:
            missing_refs.append(f"{citation['author']} ({citation['year']})")

    if not quiet:
        print(f"\n{'='*60}")
        print(f"Generating references file: {output_file}")
        print(f"Found {len(unique_refs)} unique references")
        if missing_refs:
            print(f"WARNING: {len(missing_refs)} citations not found in references.md")
        print(f"{'='*60}\n")

    # Sort references alphabetically by primary author
    sorted_refs = sorted(unique_refs.values(), key=lambda x: x.split('.')[0].strip().lower())

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("## References\n\n")
        f.write(f"<!-- Generated from: {', '.join(pf.name for pf in paper_files)} -->\n")
        f.write(f"<!-- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n")
        f.write(f"<!-- Total references: {len(sorted_refs)} -->\n\n")

        for ref in sorted_refs:
            f.write(f"{ref}\n\n")

        if missing_refs:
            f.write("\n<!-- MISSING REFERENCES (Not found in references.md) -->\n")
            f.write("<!-- Please add these to references.md: -->\n\n")
            for missing in sorted(set(missing_refs)):
                f.write(f"<!-- {missing} -->\n")

    if not quiet:
        print(f"[OK] References file generated: {output_file}")
        print(f"  - {len(sorted_refs)} references included")
        if missing_refs:
            print(f"  - {len(set(missing_refs))} missing citations noted in comments")
            print(f"\nMissing references:")
            for missing in sorted(set(missing_refs)):
                print(f"  - {missing}")

    return len(sorted_refs), len(set(missing_refs))

def main():
    """Main function to extract citations with command-line argument support."""
    parser = argparse.ArgumentParser(
        description='Extract citations from markdown files and match them to references.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python citation_extractor.py                    # Scan all .md files
  python citation_extractor.py final.md          # Scan specific file
  python citation_extractor.py -o output.txt     # Custom output file
  python citation_extractor.py final.md -o citations.txt
  python citation_extractor.py final.md -r final_references.md  # Generate references file
  python citation_extractor.py final.md -r final_refs.md -q     # Quiet mode
        """
    )

    parser.add_argument('files', nargs='*',
                       help='Specific markdown files to scan (default: all .md files)')
    parser.add_argument('-o', '--output', default='citations_found.txt',
                       help='Output file name (default: citations_found.txt)')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Suppress progress messages')
    parser.add_argument('-a', '--append', action='store_true',
                       help='Append to output file instead of overwriting')
    parser.add_argument('-r', '--generate-references', metavar='REFFILE',
                       help='Generate a references.md file containing only citations from scanned file(s)')

    args = parser.parse_args()

    # Determine which files to scan
    current_dir = Path('.')

    if args.files:
        # Scan specific files
        paper_files = [Path(f) for f in args.files if f.endswith('.md')]
        if not paper_files:
            print("Error: No valid .md files specified")
            return
    else:
        # Scan all .md files, excluding references and citations files
        paper_files = []
        for file in current_dir.glob('*.md'):
            if (file.name not in ['references.md'] and
                not file.name.startswith('citations_') and
                not file.is_dir()):
                paper_files.append(file)

    if not args.quiet:
        print(f"Found {len(paper_files)} paper file(s) to scan")
        for f in paper_files:
            print(f"  - {f.name}")

    # Load references
    references = load_references()
    if not args.quiet:
        print(f"\nLoaded {len(references)} reference entries")

    # Extract citations from all files
    all_citations = []
    for file in paper_files:
        if not args.quiet:
            print(f"\nScanning {file.name}...")
        citations = extract_citations_from_file(file, verbose=not args.quiet)
        all_citations.extend(citations)
        if not args.quiet:
            parenthetical = sum(1 for c in citations if c['type'] == 'parenthetical')
            in_prose = sum(1 for c in citations if c['type'] == 'in-prose')
            possessive = sum(1 for c in citations if c['type'] == 'possessive')
            print(f"  Found {len(citations)} citations ({parenthetical} parenthetical, {in_prose} in-prose, {possessive} possessive)")

    if not args.quiet:
        print(f"\n{'='*60}")
        print(f"Total citations found: {len(all_citations)}")
        total_parenthetical = sum(1 for c in all_citations if c['type'] == 'parenthetical')
        total_in_prose = sum(1 for c in all_citations if c['type'] == 'in-prose')
        total_possessive = sum(1 for c in all_citations if c['type'] == 'possessive')
        print(f"  Parenthetical: {total_parenthetical}")
        print(f"  In-prose: {total_in_prose}")
        print(f"  Possessive: {total_possessive}")
        print(f"{'='*60}\n")

    # Write results to file
    mode = 'a' if args.append else 'w'

    with open(args.output, mode, encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Citation Extraction Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Files scanned: {', '.join(pf.name for pf in paper_files)}\n")
        f.write(f"Total citations: {len(all_citations)}\n")
        f.write(f"{'='*80}\n\n")

        # Group citations by file for better organization
        citations_by_file = {}
        for citation in all_citations:
            file_name = citation['file']
            if file_name not in citations_by_file:
                citations_by_file[file_name] = []
            citations_by_file[file_name].append(citation)

        for file_name in sorted(citations_by_file.keys()):
            f.write(f"\n{'#'*80}\n")
            f.write(f"FILE: {file_name}\n")
            f.write(f"{'#'*80}\n\n")

            file_citations = citations_by_file[file_name]

            for i, citation_data in enumerate(file_citations, 1):
                f.write(f"Citation {i} [{citation_data['type'].upper()}]:\n")
                f.write(f"Line: {citation_data['line']}\n")
                f.write(f"Citation: {citation_data['citation']}\n")
                f.write("\nContext:\n")
                f.write(f"{citation_data['context']}\n\n")

                # Look up reference
                ref = match_citation_to_reference(
                    citation_data['author'],
                    citation_data['year'],
                    references
                )

                if ref:
                    f.write("Reference:\n")
                    f.write(f"{ref}\n")
                else:
                    f.write(f"Reference: NOT FOUND for '{citation_data['author']} {citation_data['year']}'\n")

                f.write(f"{'-'*60}\n\n")

    if not args.quiet:
        print(f"Results {'appended to' if args.append else 'written to'} {args.output}")

    # Generate references file if requested
    if args.generate_references:
        if not all_citations:
            print("Warning: No citations found, cannot generate references file")
        else:
            generate_references_file(
                all_citations,
                references,
                args.generate_references,
                paper_files,
                quiet=args.quiet
            )

def test_citation_extraction():
    """Test citation extraction and matching."""
    # Test data
    test_content = """
    This is a test (Mackie 1977) and (Blackburn 1993).
    Also (Glenn, Forthcoming) and Goldman (1979).
    """

    # Mock references
    test_references = {
        "Mackie": "Mackie, J. L. 1977. *Ethics: Inventing Right and Wrong*. London: Penguin Books.",
        "Mackie 1977": "Mackie, J. L. 1977. *Ethics: Inventing Right and Wrong*. London: Penguin Books.",
        "Blackburn": "Blackburn, Simon. 1993. *Essays in Quasi-Realism*. New York: Oxford University Press.",
        "Blackburn 1993": "Blackburn, Simon. 1993. *Essays in Quasi-Realism*. New York: Oxford University Press.",
        "Glenn": "Glenn, Patrick. Forthcoming. \"The Architecture of Failure: How Systemic Brittleness Drives Convergent Coherence to Forge Objective Truth.\"",
        "Glenn Forthcoming": "Glenn, Patrick. Forthcoming. \"The Architecture of Failure: How Systemic Brittleness Drives Convergent Coherence to Forge Objective Truth.\"",
        "Goldman": "Goldman, Alvin I. 1979. \"What Is Justified Belief?\" In *Justification and Knowledge: New Studies in Epistemology*, edited by George S. Pappas, 1–23. Dordrecht: D. Reidel.",
        "Goldman 1979": "Goldman, Alvin I. 1979. \"What Is Justified Belief?\" In *Justification and Knowledge: New Studies in Epistemology*, edited by George S. Pappas, 1–23. Dordrecht: D. Reidel.",
    }

    # Test extraction
    from pathlib import Path
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_file = Path(f.name)

    citations = extract_citations_from_file(temp_file, verbose=False)
    os.unlink(temp_file)

    print(f"Extracted {len(citations)} citations:")
    for c in citations:
        print(f"  {c['citation']} -> Author: '{c['author']}', Year: '{c['year']}'")

    # Test matching
    matched = 0
    for c in citations:
        ref = match_citation_to_reference(c['author'], c['year'], test_references)
        if ref:
            matched += 1
            print(f"  MATCHED: {c['author']} {c['year']}")
        else:
            print(f"  NOT MATCHED: {c['author']} {c['year']}")

    print(f"Matched {matched}/{len(citations)} citations")

    # Expected: all 4 should match
    assert matched == 4, f"Expected 4 matches, got {matched}"

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_citation_extraction()
    else:
        main()
