#!/usr/bin/env python3
"""
Paper Release Tagging Script

Automates versioning, committing, and tagging for paper releases.
Usage: python scripts/tag_release.py [--major|--minor|--patch] [--message "commit msg"]
"""

import subprocess
import argparse
import re
from pathlib import Path

def get_current_version():
    """Get the latest git tag version."""
    try:
        result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "v0.0.0"  # Default if no tags

def increment_version(version, bump_type):
    """Increment version number."""
    match = re.match(r'v(\d+)\.(\d+)\.(\d+)', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    
    major, minor, patch = map(int, match.groups())
    
    if bump_type == 'major':
        return f"v{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"v{major}.{minor + 1}.0"
    elif bump_type == 'patch':
        return f"v{major}.{minor}.{patch + 1}"
    else:
        return version

def main():
    parser = argparse.ArgumentParser(description='Tag a paper release')
    parser.add_argument('--major', action='store_true', help='Increment major version')
    parser.add_argument('--minor', action='store_true', help='Increment minor version')
    parser.add_argument('--patch', action='store_true', help='Increment patch version')
    parser.add_argument('--message', '-m', default='Update paper', help='Commit message')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen')
    
    args = parser.parse_args()
    
    # Determine bump type
    bump_type = None
    if args.major:
        bump_type = 'major'
    elif args.minor:
        bump_type = 'minor'
    elif args.patch:
        bump_type = 'patch'
    
    current_version = get_current_version()
    new_version = increment_version(current_version, bump_type) if bump_type else current_version
    
    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")
    print(f"Commit message: {args.message}")
    
    if args.dry_run:
        print("DRY RUN - No changes made")
        return
    
    # Stage all changes
    subprocess.run(['git', 'add', '.'], check=True)
    
    # Commit
    subprocess.run(['git', 'commit', '-m', args.message], check=True)
    
    # Tag
    subprocess.run(['git', 'tag', new_version], check=True)
    
    # Push commit and tag
    subprocess.run(['git', 'push', 'origin', 'main'], check=True)
    subprocess.run(['git', 'push', 'origin', new_version], check=True)
    
    print(f"Successfully tagged and pushed {new_version}")

if __name__ == '__main__':
    main()