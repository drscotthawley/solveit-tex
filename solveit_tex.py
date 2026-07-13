import os, subprocess, json, re, sys
from pathlib import Path
from IPython.display import HTML, display

async def get_curr_dialog_path():
    from dialoghelper.solveitskill import curr_dialog, realpath
    name = (await curr_dialog())['name']
    return f'{await realpath("/")}/{name}.ipynb'

def get_private_url(path: str):
    "Get the private URL for a file on the solveit cloud instance"
    server = os.getenv('PRIVATE_DOMAIN')
    if not server: raise ValueError("PRIVATE_DOMAIN not set")
    path = os.path.abspath(path)
    return f"https://{server}.solve.it.com{path.replace('/app/data', '/static')}"

def parse_figure(lines):
    r"""Parse markdown figure: images + optional *caption*\{attrs} inline or trailing. Per-attribute last-wins merge."""
    import re
    from pathlib import Path
    if isinstance(lines, str): lines = lines.split('\n')
    lines = [l for l in lines if l.strip()]
    if not lines: return None

    def parse_attrs(s):
        w, l = re.search(r'width=([^\s#]+)', s), re.search(r'#fig:([^\s}]+)', s)
        return {'width': w.group(1) if w else None, 'label': l.group(1) if l else None}

    image_line = lines[0]
    attrs = {}
    m = re.search(r'\\\{([^}]*)\}\s*$', image_line)
    if m: attrs = {k:v for k,v in parse_attrs(m.group(1)).items() if v}; image_line = image_line[:m.start()]

    imgs = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', image_line.strip())
    if not imgs: return None
    images = [{'path': p.strip(), **({'width': attrs['width']} if 'width' in attrs else {})} for _, p in imgs]
    caption = imgs[-1][0]
    if caption in [Path(p['path']).name for p in images] + [p['path'] for p in images]: caption = ""

    # Caption candidates: inline remainder (after images) + trailing lines
    remainder = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', '', image_line).strip()
    for text in [remainder] + [l.strip() for l in lines[1:]]:
        cm = re.search(r'\*([^*]+)\*(?:\s*\\\{([^}]*)\})?', text)
        if not cm: continue
        caption = cm.group(1)
        if cm.group(2):
            ta = {k:v for k,v in parse_attrs(cm.group(2)).items() if v}
            if 'width' in ta: attrs['width'] = ta['width']; [img.update({'width': ta['width']}) for img in images]
            if 'label' in ta: attrs['label'] = ta['label']

    return {'caption': caption, 'images': images, 'label': attrs.get('label')}


def make_figure(fig_dict: dict):
    "Generate LaTeX figure environment from image specs."
    images, caption, label = fig_dict['images'],  fig_dict.get('caption', ''), fig_dict.get('label', '')
    lines = ['\\begin{figure}[htbp]', '\\centering']  # Start figure environment
    for img in images:
        width_opt = f'[width={img["width"]}]' if 'width' in img else '[width=\\linewidth]' # Add width if specified, defalt to linewidth
        lines.append(f'\\includegraphics{width_opt}{{{img["path"]}}}')  # Include the image
    if caption: lines.append(f'\\caption{{{caption}}}')  # Add caption if provided
    if label: lines.append(f'\\label{{fig:{label}}}')  # Add label if provided
    lines.append('\\end{figure}')  # Close figure environment
    return '\n'.join(lines)

def make_list(lines: list, 
              nosep=True, # nosep: True means don't add vertical space between list items.
              ):    
    "Convert markdown list lines to LaTeX itemize/enumerate environment."
    import re 
    env = 'itemize' # default to bulleted lists. detect if they're numbered, below
    processed = []
    for line in lines:
        m = re.match(r'^([*-]\s+|\d+\.\s+)', line)
        if m:
            if re.match(r'\d+\.', m.group(1)): env = 'enumerate'
            processed.append(r'\item ' + line[len(m.group(1)):])
    out = [fr'\begin{{{env}}}']
    if nosep: out[0] += '[nosep]'
    out.extend(processed)
    out.append(fr'\end{{{env}}}')
    return '\n'.join(out)

def parse_table(lines):
    """Parse markdown table with optional caption above or below. Returns table_dict or None.
    Note: parse table doesn't care whether the caption comes first or last, *however* logic of the main export script
    only triggers table conversion when the *first line* starts with "|".  So in Markdown, the caption needs to come last.
    """
    if isinstance(lines, str): lines = lines.split('\n')
    start = 0
    while start < len(lines) and not lines[start].strip(): start += 1
    lines = lines[start:]
    caption, label = '', None
    if not lines[0].strip().startswith('|'):
        m = re.match(r'\s*\*([^*]+)\*(?:\s*\\\{#([^}]+)\})?', lines[0])
        if m: caption, label = m.group(1), m.group(2); lines = lines[1:]
    if not lines or not lines[0].startswith('|'): return None
    i = 0
    while i < len(lines) and lines[i].startswith('|'): i += 1
    if i < 3: return None
    sep = [c.strip() for c in lines[1].split('|')[1:-1]]
    aligns = ['c' if c.startswith(':') and c.endswith(':') else 'r' if c.endswith(':') else 'l' for c in sep]
    headers = [c.strip() for c in lines[0].split('|')[1:-1]]
    rows = []
    for r in lines[2:i]:
        if r.strip().startswith('| ---'): rows.append(None)   # allow for midrules
        else: rows.append([c.strip() for c in r.split('|')[1:-1]])
    if i < len(lines):
        m = re.match(r'\s*\*([^*]+)\*(?:\s*\\\{#([^}]+)\})?', lines[i])
        if m: caption, label = m.group(1), m.group(2)
    return {'headers': headers, 'rows': rows, 'alignments': aligns, 'caption': caption, 'label': label}


def md_to_latex_bold(text: str):
    return re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', text)

md_to_latex_bold('| 0.20 (champion) | **0.5151** | **0.4665** | **0.5327** | **0.6151** | 1749 |')

def md_to_latex_italic(text: str):
    return re.sub(r'\*([^*]+)\*', r'\\textit{\1}', text)

def make_table(tbl: dict):
    "Generate LaTeX table environment from parsed table dict; tabulary auto-wraps to \\linewidth so no table can overflow the page."
    col_spec = ''.join(a.upper() for a in tbl['alignments'])   # l/c/r -> L/C/R (wrapping)
    lines = [r'\begin{table}[htbp]', r'\centering']
    if tbl.get('caption'): lines.append(r'\caption{' + tbl['caption'] + '}')
    if tbl.get('label'): lines.append(r'\label{tab:' + tbl['label'] + '}')
    lines.append(r'\begin{tabulary}{\linewidth}{' + col_spec + '}')
    lines.append(r'\toprule')
    lines.append(' & '.join(tbl['headers']) + r' \\')
    lines.append(r'\midrule')
    for row in tbl['rows']:
        if row is None: lines.append(r'\midrule')
        else: lines.append(' & '.join(md_to_latex_bold(cell) for cell in row) + r' \\')
    lines.append(r'\bottomrule')
    lines.append(r'\end{tabulary}')
    lines.append(r'\end{table}')
    return md_to_latex_italic('\n'.join(lines))


def export_ordered(curr_path, output_path=None):
    """Uses user-defined syntax '#| replaces: <msg_id>' to replace earlier messages with later ones 
    msg_id be obtained in the GUI by pressing the link button.
    Valid syntax usages (with or without colons): 
        #| replaces: https://serene-vision-dives-ildq3w.solve.it.com/dialog_?name=solveit-tex/solveit-tex#_a0d44aac
        #| replaces _a0d44aac
    """
    if output_path is None: output_path = curr_path.replace('.ipynb', '-out.ipynb')
    nb = json.loads(Path(curr_path).read_text())
    
    # Pass 1: find replacements {target_id -> cell}, last-wins
    replacements = {}
    for cell in nb['cells']:
        content = ''.join(cell['source'])
        if not content.lstrip().startswith('#| export'): continue
        for line in content.split('\n'):
            if line.startswith('#| replaces:'):
                target = line.split('#')[-1].strip('_')
                replacements[target] = cell
    
    # Pass 2: walk in order, apply replacements, keep only exported
    out_cells = []
    for cell in nb['cells']:
        content = ''.join(cell['source'])
        if not content.lstrip().startswith('#| export'): continue
        cid = cell.get('id', '').strip('_')
        if cid in replacements:
            rcell = replacements[cid]
            rcontent = '\n'.join(l for l in ''.join(rcell['source']).split('\n') if not l.startswith('#| replaces'))
            lines = rcontent.split('\n')
            rcontent = [l + '\n' for l in lines[:-1]] + [lines[-1]]
            out_cells.append({**rcell, 'source': rcontent})
        else:
            if any(l.startswith('#| replaces') for l in content.split('\n')): continue  # don't re-add replacements
            out_cells.append(cell)
    
    nb['cells'] = out_cells
    Path(output_path).write_text(json.dumps(nb, indent=1))
    print(f'Exported {len(out_cells)} cells to {output_path}')
    return output_path 

def latex_clean_line(line: str) -> str:
    "Escape percent signs and replace Unicode characters with LaTeX equivalents."
    if not line.startswith('%'):
        line = re.sub(r'(?<!\\)%', r'\\%', line)
    replacements = {
        # Dashes
        '–': r'--', '—': r'---', '‐': '-', '‑': '-',
        # Smart quotes
        ''': "'", ''': "'", '"': '``', '"': "''",
        # Basic math
        '−': r'$-$', '×': r'$\times$', '÷': r'$\div$',
        '±': r'$\pm$', '∓': r'$\mp$', '·': r'$\cdot$',
        '≈': r'$\approx$', '≠': r'$\neq$', '≡': r'$\equiv$',
        '≤': r'$\leq$', '≥': r'$\geq$', '≪': r'$\ll$', '≫': r'$\gg$',
        '∝': r'$\propto$', '∞': r'$\infty$',
        '∂': r'$\partial$', '∇': r'$\nabla$', '√': r'$\sqrt{}$',
        # check marks 
        '✓': r'\checkmark',
        '✗': r'$\times$',
        # Sum/integral/product
        '∑': r'$\sum$', '∏': r'$\prod$', '∫': r'$\int$',
        # Sets & logic
        '∈': r'$\in$', '∉': r'$\notin$', '∀': r'$\forall$',
        '∃': r'$\exists$', '⊂': r'$\subset$', '⊃': r'$\supset$',
        '⊆': r'$\subseteq$', '⊇': r'$\supseteq$',
        '∩': r'$\cap$', '∪': r'$\cup$', '∅': r'$\emptyset$',
        '⊕': r'$\oplus$', '⊗': r'$\otimes$',
        '¬': r'$\neg$', '∧': r'$\wedge$', '∨': r'$\vee$',
        # Arrows
        '→': r'$\to$', '←': r'$\leftarrow$', '↔': r'$\leftrightarrow$',
        '⇒': r'$\Rightarrow$', '⇐': r'$\Leftarrow$', '⇔': r'$\Leftrightarrow$',
        '↑': r'$\uparrow$', '↓': r'$\downarrow$',
        # Geometry
        '∥': r'$\parallel$', '⊥': r'$\perp$', '∠': r'$\angle$',
        # Greek lowercase
        'α': r'$\alpha$', 'β': r'$\beta$', 'γ': r'$\gamma$',
        'δ': r'$\delta$', 'ε': r'$\epsilon$', 'ζ': r'$\zeta$',
        'η': r'$\eta$', 'θ': r'$\theta$', 'ι': r'$\iota$',
        'κ': r'$\kappa$', 'λ': r'$\lambda$', 'μ': r'$\mu$',
        'ν': r'$\nu$', 'ξ': r'$\xi$', 'π': r'$\pi$',
        'ρ': r'$\rho$', 'σ': r'$\sigma$', 'τ': r'$\tau$',
        'υ': r'$\upsilon$', 'φ': r'$\phi$', 'χ': r'$\chi$',
        'ψ': r'$\psi$', 'ω': r'$\omega$',
        # Greek uppercase (only those that differ from Latin)
        'Γ': r'$\Gamma$', 'Δ': r'$\Delta$', 'Θ': r'$\Theta$',
        'Λ': r'$\Lambda$', 'Ξ': r'$\Xi$', 'Π': r'$\Pi$',
        'Σ': r'$\Sigma$', 'Υ': r'$\Upsilon$', 'Φ': r'$\Phi$',
        'Ψ': r'$\Psi$', 'Ω': r'$\Omega$',
        # Unicode superscripts
        '⁰': r'$^{0}$', '¹': r'$^{1}$', '²': r'$^{2}$', '³': r'$^{3}$',
        '⁴': r'$^{4}$', '⁵': r'$^{5}$', '⁶': r'$^{6}$',
        '⁷': r'$^{7}$', '⁸': r'$^{8}$', '⁹': r'$^{9}$',
        '⁺': r'$^{+}$', '⁻': r'$^{-}$',
        # Unicode subscripts
        '₀': r'$_{0}$', '₁': r'$_{1}$', '₂': r'$_{2}$', '₃': r'$_{3}$',
        '₄': r'$_{4}$', '₅': r'$_{5}$', '₆': r'$_{6}$',
        '₇': r'$_{7}$', '₈': r'$_{8}$', '₉': r'$_{9}$',
        # Misc typography
        '…': r'\ldots', '°': r'$^\circ$',
        '′': r"$'$", '″': r"$''$",
        '•': r'$\bullet$', '§': r'\S', '¶': r'\P',
        '†': r'$\dagger$', '‡': r'$\ddagger$',
        '©': r'\textcopyright', '®': r'\textregistered', '™': r'\texttrademark',
        # Invisible chars — just strip them
        '­': '', '\u200b': '', '\ufeff': '',
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    return line

def export_ipynb_to_tex(ipynb_path: str, output_path: str = None, ordered=True):
    r"""Export a Solveit dialog (.ipynb) to a compilable LaTeX file.
    Cells are emitted in document order, each preceded by a `% <cell-id>` comment.
    The `## Abstract` cell emits `\begin{document}`, dividing preamble from document body."""

    ipynb_path = os.path.expanduser(ipynb_path)

    if ordered:  # Export preserving "#| replaces" ordering. Writes to -out.ipynb first. That becomes the input file 
        ipynb_path = export_ordered(ipynb_path)
        
    output_path = os.path.expanduser(output_path) if output_path else Path(ipynb_path).with_suffix('.tex')
    if ordered: output_path = str(output_path).replace('-out.tex', '.tex')
    print("output_path =",output_path)

    nb = json.loads(Path(ipynb_path).read_text())
    out = []
    title = 'TITLE NOT FOUND'
    for cell in nb['cells']:
        content = ''.join(cell['source'])
        content = md_to_latex_bold(content)
        if '#| export' not in content: continue

        filtered = '\n'.join(l for l in content.split('\n') if not l.startswith('#| '))
        out.append(f'% {cell["id"]}')

        if cell['cell_type'] == 'raw':
            out.append(filtered)
            continue
        lines = filtered.split('\n')
        lines = [latex_clean_line(line) for line in lines]

        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('# ') and not line.startswith('## '):
                title = f'{line[2:].strip()}'
            elif line.startswith('\\author{'):
                out.append(line)
                while i < len(lines) and not lines[i].strip().endswith('}'):
                    i += 1
                    if i < len(lines): out.append(lines[i])
            elif line == '## Abstract':
                out.append(f'\\title{{{title}}}\n')
                out.append('\\begin{document}\n\n\\maketitle\n')
                out.append('\\begin{abstract}\n')
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    out.append(lines[i])
                    i += 1
                out.append('\\end{abstract}\n')
                continue
            elif line == '## References':
                out.append('\\small\n')
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    l = lines[i]
                    if l.strip().startswith('\\bibliographystyle'):
                        out.append(l + '\n')
                    bib_match = re.search(r'(\w+)\.bib', l)
                    if bib_match:
                        out.append(f'\\bibliography{{{bib_match.group(1)}}}\n')
                    i += 1
                continue
            elif line.startswith('### '):
                out.append(f'\\subsection{{{line[4:].strip()}}}\n')
            elif line.startswith('#### '):
                out.append(f'\\subsubsection{{{line[4:].strip()}}}\n')
            elif line.startswith('#####'):   
                out.append(re.sub(r'^#+\s*(.*)', r'\\textbf{\1}', line) + '\n')  # anything smaller becomes bold
            elif line.startswith('## '):
                out.append(f'\\section{{{line[3:].strip()}}}\n')
            elif re.match(r'^[*-]\s+|^\d+\.\s+', line):  # list handling (no nested list support yet!)
                list_lines = [line]
                i += 1
                while i < len(lines) and re.match(r'^[*-]\s+|^\d+\.\s+', lines[i]):
                    list_lines.append(lines[i])
                    i += 1
                out.append(make_list(list_lines))
                continue
            elif line.startswith('|'):    # table handling
                # Collect table lines
                table_lines = []
                while i < len(lines) and lines[i].startswith('|'):
                    table_lines.append(lines[i])
                    i += 1
                # Check for caption line
                if i < len(lines) and re.match(r'\s*\*', lines[i]):
                    table_lines.append(lines[i])
                    i += 1
                # Parse and convert
                tbl_dict = parse_table(table_lines)
                if tbl_dict:
                    out.append(make_table(tbl_dict))
                continue  # Skip the i += 1 at the end    
            else:         # figures
                fig_dict = parse_figure(line)
                if fig_dict:
                    out.append(make_figure(fig_dict))
                else:
                    out.append(line)

            i += 1

    final = '\\documentclass{article}\n'
    # packages we definitely want. Hopefully these will be compatible with style files, etc.
    packages = ['graphicx','booktabs','enumitem','tabulary']
    for p in packages: final += '\\usepackage{' + p + '}\n'
    #final += '\\usepackage{graphicx}\n\\usepackage{booktabs}\n\\usepackage{enumitem}\n\\usepackage{tabulary}\n'
    final += '\n'.join(out) + '\n\n'
    final += '\\end{document}\n'
    final = md_to_latex_italic(final)
    
    Path(output_path).write_text(final)
    print(f'Created {output_path}')
    output_url = get_private_url(output_path)
    display(HTML(f'<a href="{output_url}" target="_blank">{output_url}</a>'))

def compile_latex(tex_file: str, cwd: str = '.'):
    "Run full LaTeX compilation: pdflatex → bibtex → pdflatex → pdflatex"

    cwd = os.path.expanduser(cwd)
    tex_file = os.path.expanduser(tex_file)
    
    # Make path absolute before splitting
    full_tex_path = os.path.abspath(os.path.join(cwd, tex_file))
    work_dir = os.path.dirname(full_tex_path)
    
    base_name = os.path.splitext(os.path.basename(full_tex_path))[0]
    tex_content = Path(full_tex_path).read_text()
    bib_match = re.search(r'\\bibliography\{([^}]+)\}', tex_content)
    
    print("Running pdflatex (pass 1)...")
    r1 = subprocess.run(f'pdflatex -halt-on-error {full_tex_path}',
                   shell=True, cwd=work_dir, capture_output=True, text=True)
    if r1.returncode != 0:
        print(f"  FAILED:\n{r1.stdout[-3000:]}")
        return
    
    if bib_match:
        bib_name = bib_match.group(1)
        print(f"\nRunning bibtex ({bib_name})...")
        r = subprocess.run(f'bibtex {base_name}',
                          shell=True, cwd=work_dir, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  FAILED:\n{r.stdout}")
            return
    
    for i in [2, 3]:
        print(f"\nRunning pdflatex (pass {i})...")
        r = subprocess.run(f'pdflatex -halt-on-error {full_tex_path}',
                       shell=True, cwd=work_dir, capture_output=True, text=True, errors='replace')
        if r.returncode != 0:
            print(f"  FAILED:\n{r.stdout[-3000:]}")
            return

    pdf_path = full_tex_path.replace('.tex', '.pdf') 
    pdf_url = get_private_url(pdf_path)
    print(f"\nSuccess!")
    print(f"File: {pdf_path}")
    print(f"PDF url: {pdf_url}")
    sys.stdout.flush() 
    display(HTML(f'<a href="{pdf_url}" target="_blank">{pdf_url}</a>'))

async def current_to_pdf():
    """
    Wrapper that converts the current dialogue to PDF and prints the private URL for it.
    Usage: await current_to_pdf()
    """
    curr_dialog_path = await get_curr_dialog_path()
    export_ipynb_to_tex(curr_dialog_path)
    display(HTML(f'<br>'))
    compile_latex(curr_dialog_path.replace('.ipynb', '.tex'))

def create_submission_package(project_dir:str='.'): 
    "Make a .tar.gz archive suitable for submission to arxiv, etc"
    import shutil, tarfile
    from rgapi.skill import fd
    
    extensions = ['tex','png','jpg','tikz','eps','sty','bib','bst']
    project_path = Path(project_dir).expanduser().resolve()
    project_name = project_path.name
    tmp_dir = Path(f'/tmp/{project_name}')
    if tmp_dir.exists(): shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    files = [Path(project_path) / f for f in fd(project_path, ext=extensions)]
    print("Files included:\n",[str(f) for f in files])
    for f in files:  
        dest = tmp_dir / f.relative_to(project_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    pkg_path = Path(project_path) / f'{project_name}.tar.gz'
    with tarfile.open(pkg_path, 'w:gz') as tar:
        tar.add(tmp_dir, arcname=project_name)
    pkg_url = get_private_url(str(pkg_path))
    display(HTML(f'<a href="{pkg_url}" target="_blank">{pkg_url}</a>'))
    return str(pkg_path)

from pyskills import allow 

allow(export_ipynb_to_tex)
allow(current_to_pdf)
allow(compile_latex) 
allow(create_submission_package)
