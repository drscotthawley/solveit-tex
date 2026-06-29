import os, subprocess, json, re, sys
from pathlib import Path
from IPython.display import HTML, display
def get_private_url(path: str):
    "Get the private URL for a file on the solveit cloud instance"
    server = os.getenv('PRIVATE_DOMAIN')
    if not server: raise ValueError("PRIVATE_DOMAIN not set")
    path = os.path.abspath(path)
    return f"https://{server}.solve.it.com{path.replace('/app/data', '/static')}"
def make_figure(images: list[dict], caption: str = "", label: str = ""):
    "Generate LaTeX figure environment from image specs."
    lines = ['\\begin{figure}[htbp]', '\\centering']  # Start figure environment
    for img in images:
        width_opt = f'[width={img["width"]}]' if 'width' in img else ''  # Add width if specified
        lines.append(f'\\includegraphics{width_opt}{{{img["path"]}}}')  # Include the image
    if caption: lines.append(f'\\caption{{{caption}}}')  # Add caption if provided
    if label: lines.append(f'\\label{{fig:{label}}}')  # Add label if provided
    lines.append('\\end{figure}')  # Close figure environment
    return '\n'.join(lines)

def parse_figure(line: str):
    "Parse markdown figure syntax: ![caption](path1,path2){width=X% #fig:label}"
    import re
    m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)(?:\{([^}]*)\})?$', line.strip())
    if not m: return None
    
    caption = m.group(1)
    paths = [p.strip() for p in m.group(2).split(',')]
    attrs = m.group(3) or ''
    
    # If caption is just a filename (matches any of the paths), treat as no caption
    if caption:
        path_basenames = [Path(p).name for p in paths]
        if caption in path_basenames or caption in paths:
            caption = ""
    
    width_m = re.search(r'width=([^\s#]+)', attrs)
    label_m = re.search(r'#fig:([^\s}]+)', attrs)
    width = width_m.group(1) if width_m else None
    label = label_m.group(1) if label_m else None
    
    images = [{'path': p, 'width': width} if width else {'path': p} for p in paths]
    return {'caption': caption, 'images': images, 'label': label}

def export_ipynb_to_tex(ipynb_path: str, output_path: str = None):
    r"""Export a Solveit dialog (.ipynb) to a compilable LaTeX file.
    Cells are emitted in document order, each preceded by a `% <cell-id>` comment.
    The `## Abstract` cell emits `\begin{document}`, dividing preamble from document body."""

    ipynb_path = os.path.expanduser(ipynb_path)
    output_path = os.path.expanduser(output_path) if output_path else Path(ipynb_path).with_suffix('.tex')

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
                    out.append(f'\\bibliographystyle{{unsrt}}\n\\bibliography{{{bib_match.group(1)}}}\n')
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    i += 1
                continue
            elif line.startswith('### '):
                out.append(f'\\subsection{{{line[4:].strip()}}}\n')
            elif line.startswith('## '):
                out.append(f'\\section{{{line[3:].strip()}}}\n')
            else:
                fig = parse_figure(line)
                if fig:
                    out.append(make_figure(fig['images'], fig['caption'], fig['label']))
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
    from dialoghelper.solveitskill import curr_dialog, realpath

    name = (await curr_dialog())['name']
    path = f'{await realpath("/")}/{name}.ipynb'
    export_ipynb_to_tex(path)
    display(HTML(f'<br>'))
    compile_latex(path.replace('.ipynb', '.tex'))
from pyskills import allow 

allow(export_ipynb_to_tex)
allow(current_to_pdf)
allow(compile_latex)
