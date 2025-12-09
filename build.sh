#!/bin/bash
# Build script for the physics paper
# Compiles draft.tex to draft.pdf using pdflatex and bibtex
# Auxiliary files are placed in paper/ directory
# Previous versions are saved in versions/ directory with timestamp

echo "Building paper..."

# Create paper directory if it doesn't exist
mkdir -p paper

# Create versions directory if it doesn't exist
mkdir -p versions

# Save current versions with timestamp (YYYY-MM-DD-HHMM format)
if [ -f draft.tex ] || [ -f draft.pdf ]; then
  TIMESTAMP=$(date +"%Y-%m-%d-%H%M")
  
  if [ -f draft.tex ]; then
    cp draft.tex "versions/draft.tex.${TIMESTAMP}"
    echo "Saved backup: versions/draft.tex.${TIMESTAMP}"
  fi
  
  if [ -f draft.pdf ]; then
    cp draft.pdf "versions/draft.pdf.${TIMESTAMP}"
    echo "Saved backup: versions/draft.pdf.${TIMESTAMP}"
  fi
fi

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
echo "Previous versions saved in versions/ directory"

# Clean up auxiliary files from root (keep them in paper/ for reference)
echo "Cleaning up auxiliary files from root..."
rm -f draft.aux draft.bbl draft.blg draft.log draft.out
echo "Cleanup complete!"