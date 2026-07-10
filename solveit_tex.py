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

def parse_figure(line: str):
    r"""Parse markdown figure syntax with multiple images on one line: ![alt1](img1.png) ![alt2](img2.png)\{width=45% #fig:label}
     Images on one line get grouped into a single figure, with the final caption and label being the one used for the group"""
    import re
    
    # Look for escaped attributes at the end: \{...}
    attrs = ''
    attr_match = re.search(r'\\\{([^}]*)\}\s*$', line)
    if attr_match:
        attrs = attr_match.group(1)
        line = line[:attr_match.start()]  # Remove the attributes part
    
    # Find all image patterns on the line
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(pattern, line.strip())
    
    if not matches: return None
    
    images = []
    caption = ""
    
    for i, (alt, path) in enumerate(matches):
        img = {'path': path.strip()}
        images.append(img)
        
        # Last image sets the caption and label
        if i == len(matches) - 1:
            caption = alt
    
    # Extract width and label from attributes
    width_m = re.search(r'width=([^\s#]+)', attrs)
    label_m = re.search(r'#fig:([^\s}]+)', attrs)
    width = width_m.group(1) if width_m else None
    label = label_m.group(1) if label_m else None
    
    # Apply width to all images if specified
    if width:
        for img in images:
            img['width'] = width
    
    # If caption is just a filename, treat as no caption
    if caption:
        path_basenames = [Path(p['path']).name for p in images]
        if caption in path_basenames or caption in [p['path'] for p in images]:
            caption = ""
    
    return {'caption': caption, 'images': images, 'label': label}

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

def parse_table(lines):
    """Parse markdown table with optional caption. Returns table_dict or None."""
    if isinstance(lines, str): lines = lines.split('\n')
    start = 0
    while start < len(lines) and not lines[start].strip(): start += 1
    lines = lines[start:]
    if not lines or not lines[0].startswith('|'): return None
    i = 0
    while i < len(lines) and lines[i].startswith('|'): i += 1
    if i < 3: return None
    sep = [c.strip() for c in lines[1].split('|')[1:-1]]
    aligns = ['c' if c.startswith(':') and c.endswith(':') else 'r' if c.endswith(':') else 'l' for c in sep]
    headers = [c.strip() for c in lines[0].split('|')[1:-1]]
    rows = [[c.strip() for c in r.split('|')[1:-1]] for r in lines[2:i]]
    caption, label = '', None
    if i < len(lines):
        m = re.match(r'\s*\*([^*]+)\*(?:\s*\\\{#([^}]+)\})?', lines[i])
        if m: caption, label = m.group(1), m.group(2)
    return {'headers': headers, 'rows': rows, 'alignments': aligns, 'caption': caption, 'label': label}

def md_to_latex_bold(text: str):
    return re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', text)

def make_table(tbl: dict):
    "Generate LaTeX table environment from parsed table dict."
    col_spec = ''.join(tbl['alignments'])
    lines = [f'\\begin{{table}}[htbp]', '\\centering', f'\\begin{{tabular}}{{{col_spec}}}', '\\hline']
    lines.append(' & '.join(tbl['headers']) + ' \\\\')
    lines.append('\\hline')
    for row in tbl['rows']:
        lines.append(' & '.join(md_to_latex_bold(cell) for cell in row) + ' \\\\')
    lines.extend(['\\hline', '\\end{tabular}'])
    if tbl.get('caption'): lines.append(f'\\caption{{{tbl["caption"]}}}')
    if tbl.get('label'): lines.append(f'\\label{{tab:{tbl["label"]}}}')
    lines.append('\\end{table}')
    return '\n'.join(lines)

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

    for cell in nb['cells']:
        content = ''.join(cell['source'])

        if '#| export' not in content:
            continue

        filtered = '\n'.join(l for l in content.split('\n') if not l.startswith('#| '))
        out.append(f'% {cell["id"]}')

        if cell['cell_type'] == 'raw':
            out.append(filtered)
            continue

        lines = filtered.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith('# ') and not line.startswith('## '):
                out.append(f'\\title{{{line[2:].strip()}}}\n')
            elif line.startswith('\\author{'):
                out.append(line)
                while i < len(lines) and not lines[i].strip().endswith('}'):
                    i += 1
                    if i < len(lines):
                        out.append(lines[i])
            elif line == '## Abstract':
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
                bib_match = re.search(r'(\w+)\.bib', content)
                if bib_match:
                    #out.append(f'\\bibliographystyle{{unsrt}}\n')
                    out.append(f'\\bibliography{{{bib_match.group(1)}}}\n')
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    i += 1
                continue
            elif line.startswith('### '):
                out.append(f'\\subsection{{{line[4:].strip()}}}\n')
            elif line.startswith('## '):
                out.append(f'\\section{{{line[3:].strip()}}}\n')
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

    final = '\\documentclass{article}\n\\usepackage{graphicx}\n\n'
    final += '\n'.join(out) + '\n\n'
    final += '\\end{document}\n'
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
                       shell=True, cwd=work_dir, capture_output=True, text=True)
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

from pyskills import allow 

allow(export_ipynb_to_tex)
allow(current_to_pdf)
allow(compile_latex)
