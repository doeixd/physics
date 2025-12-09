#!/usr/bin/env python3
"""
Script to replace Unicode characters in draft.tex with LaTeX equivalents.
"""

import re

# Read the file
with open('draft.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Replacements
replacements = {
    '∼': r'\sim',
    '≲': r'\lesssim',
    '≈': r'\approx',
    '≤': r'\leq',
    '≥': r'\geq',
    '≠': r'\neq',
    '×': r'\times',
    '∞': r'\infty',
    '∂': r'\partial',
    '∫': r'\int',
    '∑': r'\sum',
    '√': r'\sqrt',
    'π': r'\pi',
    'μ': r'\mu',
    'ℏ': r'\hbar',
    'ψ': r'\psi',
    'ℓ': r'\ell',
    '²': r'^{2}',
    '³': r'^{3}',
    '⁻': r'^{-}',
    '₀': r'_{0}',
}

for unicode_char, latex_cmd in replacements.items():
    content = content.replace(unicode_char, latex_cmd)

# Write back
with open('draft.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("Unicode replacements completed.")