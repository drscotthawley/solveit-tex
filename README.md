# solveit-tex

Convert [Solveit](https://solveit.fast.ai) dialogs to LaTeX and compile PDFs.  

The motivation is to facilitate [Human-Authored, Computer-Interrogated (HACI)](https://share.solveit.pub/d/35bfa209be24e19292d5b63d984d4b7f) workflows in which the AI is used to prompt the user into refining the content written by the user.

## Prerequisites

You need a working TeX installation. Install TeX Live:

```bash
# Ubuntu/Debian
sudo apt-get install texlive-full

# macOS (using Homebrew)
brew install --cask mactex

# Or use the cross-platform installer from https://tug.org/texlive/
```

Verify installation:
```bash
pdflatex --version
bibtex --version
```

## Installation

```bash
pip install git+https://github.com/drscotthawley/solveit-tex.git
```

Or clone and install in editable mode:
```bash
git clone https://github.com/drscotthawley/solveit-tex.git
cd solveit-tex
pip install -e .
```

## Usage

### Basic workflow

```python
from solveit_tex import export_ipynb_to_tex, compile_latex

# Convert a Solveit dialog to LaTeX
export_ipynb_to_tex('my_dialog.ipynb', 'output.tex')

# Compile to PDF (runs pdflatex → bibtex → pdflatex → pdflatex)
compile_latex('output.tex', cwd='.')
```

### Dialog format

Your Solveit dialog should use these conventions:

- **Raw cells** before the abstract become the LaTeX preamble (e.g., `\usepackage` commands)
- **`# Title`** becomes `\title{...}`
- **`\author{...}`** blocks are preserved
- **`## Abstract`** section becomes `\begin{abstract}...\end{abstract}`
- **`## Section Name`** becomes `\section{Section Name}`
- **`### Subsection Name`** becomes `\subsection{Subsection Name}`
- **`## References`** section triggers bibliography processing

Only cells marked with `#| export` are included in the output.

### Example

See the `example/` directory for a complete NeurIPS-style paper:

```bash
cd example
# Run build_neurips.ipynb in Solveit, or:
python -c "
from solveit_tex import export_ipynb_to_tex, compile_latex
export_ipynb_to_tex('neurips_2026.ipynb')
compile_latex('neurips_2026.tex', cwd='.')
"
```

## License

MIT
