#!/bin/bash
# Build script for the physics paper
# Compiles draft.tex to draft.pdf using pdflatex and bibtex
# Auxiliary files are placed in paper/ directory

echo "Building paper..."

# Create paper directory if it doesn't exist
mkdir -p paper

# First pdflatex run (aux files go to paper/)
echo "Running pdflatex (1/3)..."
pdflatex -aux-directory=paper -output-directory=. draft.tex

# BibTeX for references (looks for aux in paper/)
echo "Running bibtex..."
bibtex paper/draft

# Second pdflatex run
echo "Running pdflatex (2/3)..."
pdflatex -aux-directory=paper -output-directory=. draft.tex

# Third pdflatex run
echo "Running pdflatex (3/3)..."
pdflatex -aux-directory=paper -output-directory=. draft.tex

echo "Build complete! PDF generated as draft.pdf"
echo "Auxiliary files are in paper/ directory"

# Clean up auxiliary files from root (keep them in paper/ for reference)
echo "Cleaning up auxiliary files from root..."
rm -f draft.aux draft.bbl draft.blg draft.log draft.out
echo "Cleanup complete!"