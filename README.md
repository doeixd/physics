# Deterministic Information-Driven Collapse: A Testable ψ-Ontic Interpretation with Minimal Non-Locality

[![GitHub](https://img.shields.io/badge/GitHub-Repo-blue)](https://github.com/doeixd/physics)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/doeixd/physics)

## Abstract

This repository contains the LaTeX source and supporting code for the paper "Deterministic Information-Driven Collapse: A Testable ψ-Ontic Interpretation with Minimal Non-Locality" by Patrick Glenn. The paper proposes a deterministic, ψ-ontic solution to the quantum measurement problem, deriving the Born rule from apparatus microstate typicality. It introduces a collapse mechanism driven by information integration thresholds and makes testable predictions, including reduced variance in squeezed-apparatus measurements.

The framework achieves minimal non-locality for a deterministic single-outcome interpretation, preserving measurement independence while avoiding hidden variables in particles.

## Repository Structure

```
physics/
├── CLAUDE.md              # Main guide and instructions
├── draft.tex              # LaTeX source for the paper
├── references.bib         # Bibliography
├── draft.pdf              # Compiled PDF (generated)
├── dii/                   # DII framework implementation
│   ├── dii_framework.py   # Core simulation code
│   ├── test_dii_framework.py  # Unit tests
│   ├── examples_dii.py    # Example simulations
│   └── requirements.txt   # Python dependencies
├── scripts/               # Utility scripts
│   ├── citation_extractor.py
│   ├── paper_converter.py
│   ├── pdf_assembler.py
│   ├── references_organizer.py
│   ├── release.py         # Markdown-to-PDF pipeline
│   └── tag_release.py     # Versioning and tagging script
├── docs/                  # Documentation
│   ├── CLAUDE.old.md
│   ├── CLAUDE_CRITICAL_ADDITIONS.md
│   ├── IMPROVEMENT_PLAN.md
│   ├── outline.md
│   └── r.md
├── paper/                 # LaTeX auxiliary files
│   ├── draft.tex.bak
│   ├── draft_appendix_b.tex
│   ├── draft.aux
│   ├── draft.bbl
│   ├── draft.blg
│   ├── draft.log
│   ├── draft.out
│   └── draft.txt
├── build/                 # Generated outputs
│   └── compile_log.txt
├── tests/                 # Additional tests
└── .claude/               # AI tool configurations
    ├── edits/
    └── settings.local.json
```

## Installation and Setup

### Prerequisites
- Python 3.8+
- LaTeX distribution (e.g., TeX Live, MiKTeX)
- Git

### Clone the Repository
```bash
git clone https://github.com/doeixd/physics
cd physics
```

### Install Python Dependencies
```bash
pip install -r dii/requirements.txt
```

### Build the Paper
Compile the LaTeX source to PDF:
```bash
pdflatex draft.tex
bibtex draft
pdflatex draft.tex
pdflatex draft.tex
```

Alternatively, use the release script for advanced options:
```bash
python scripts/release.py draft.md --format latex  # If converting from markdown
```

## Usage

### Running Simulations
Execute the DII framework simulations:
```bash
python dii/dii_framework.py
```

Run examples:
```bash
python dii/examples_dii.py
```

### Tagging and Releasing
Use the tagging script for versioned releases:
```bash
python scripts/tag_release.py --minor -m "Updated results section"
```

This commits changes, creates a version tag (e.g., v1.1.0), and pushes to GitHub, triggering an automatic PDF build and release.

### Key Results and Predictions
- **Born Rule Derivation**: Emerges from typicality over apparatus microstates using Haar measure and Porter-Thomas statistics.
- **Collapse Mechanism**: Triggered by information integration exceeding a threshold Δ_crit, derived from redundancy principles.
- **Testable Predictions**:
  - Squeezed-apparatus measurements show reduced outcome variance (∝ e^{-4Nr}).
  - Apparatus-dependent outcomes without violating no-signaling.
  - Experimental protocols for verifying the framework.

## Contributing

- Report issues or suggest improvements via [GitHub Issues](https://github.com/doeixd/physics/issues).
- Pull requests are welcome—please follow the guidelines in `CLAUDE.md`.
- For major changes, open an issue first to discuss.

## Citation

If you use this work, please cite:

```bibtex
@article{glenn2025didi,
  title={Deterministic Information-Driven Collapse: A Testable ψ-Ontic Interpretation with Minimal Non-Locality},
  author={Glenn, Patrick},
  journal={arXiv preprint},
  year={2025}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Repository**: [https://github.com/doeixd/physics](https://github.com/doeixd/physics)
