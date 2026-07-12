# solveit-tex

Convert [Solveit](https://solveit.fast.ai) dialogs to LaTeX and compile PDFs.  

The motivation is to facilitate [Human-Authored, Computer-Interrogated (HACI)](https://share.solveit.pub/d/35bfa209be24e19292d5b63d984d4b7f) workflows in which the AI is used to prompt the user into refining their own content.

## Prerequisites

`solveit-tex` needs a working `pdflatex` (and `bibtex`). On Solveit, the
easiest way to get these is via TinyTeX, which Quarto can install for you.
(Quarto is already available on Solveit.)

```bash
# Install TinyTeX (provides pdflatex, bibtex, tlmgr, etc.)
quarto install tinytex
```

TinyTeX installs into `~/.TinyTeX/` but its binaries may not be on your
`PATH`. You can either update your `$PATH` accordingly, e.g., add this line to your `~/.bashrc` file:
```bash
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
```
Or, what I like to do is to symlink `pdflatex` (and any other tools you need) into a directory
that is on your PATH:

```bash
ln -s ~/.TinyTeX/bin/*/pdflatex ~/.local/bin/
ln -s ~/.TinyTeX/bin/*/bibtex ~/.local/bin/
ln -s ~/.TinyTeX/bin/*/tlmgr ~/.local/bin/
```

Verify:

```bash
pdflatex --version
bibtex --version
```

### Missing LaTeX packages

TinyTeX is minimal, so a compile may fail with a missing font or package.
Install what's needed with `tlmgr`. For example, the NeurIPS example needs
the `cm-super` fonts:

```bash
tlmgr install cm-super
updmap-sys
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

### Suggested Hotkey: Cmd+Shift+P 
Copy the  `CRAFT.js` settings to your paper directory or your home directory in order to enable compilation via Cmd-Shift-P.
That will create a dialog message that executes the conversion and gives you the URL(s) to view it. 

### Adding Features (WIP)
You can always just write raw LaTeX and it'll go through fine. Question is whether you want to see anything meaningful in SolveIT also.

- [X] Figures. Multiple figures on one line get grouped together in one figure, final caption "wins".
- [X] Tables. But needs documentation
- [X] Lists: Simple bulleted and/or numbered lists. No nested lists yet. 
- [X] Handling other bibliography styles 
- [X] Creating a (.tar.gz) "submission package", e.g. for arXiv
- [ ] Numbering equations


## License

MIT
