import os, subprocess, json, re, sys
from pathlib import Path
from IPython.display import HTML, display
def export_ipynb_to_tex(ipynb_path: str, output_path: str = None):
    "Export a Solveit dialog (.ipynb) to a compilable LaTeX file."
    
    ipynb_path = os.path.expanduser(ipynb_path)
    output_path = os.path.expanduser(output_path) if output_path else Path(ipynb_path).with_suffix('.tex')

    nb = json.loads(Path(ipynb_path).read_text())
    preamble_lines = []
    body_lines = []
    past_abstract = False

    for cell in nb['cells']:
        content = ''.join(cell['source'])

        if cell['cell_type'] != 'raw' and '#| export' not in content:
            continue

        if cell['cell_type'] == 'raw' and '#| export' not in content:
            continue

        filtered = '\n'.join(l for l in content.split('\n') if not l.startswith('#| '))

        if cell['cell_type'] == 'raw' and not past_abstract:
            preamble_lines.append(filtered)
            continue

        lines = filtered.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith('# ') and not line.startswith('## '):
                preamble_lines.append(f'\\title{{{line[2:].strip()}}}\n')
            elif line.startswith('\\author{'):
                preamble_lines.append(line)
                while i < len(lines) and not lines[i].strip().endswith('}'):
                    i += 1
                    if i < len(lines):
                        preamble_lines.append(lines[i])
                preamble_lines.append('\\begin{document}\n\\maketitle\n')
            elif line == '## Abstract':
                preamble_lines.append('\\begin{abstract}\n')
                i += 1
                while i < len(lines) and not lines[i].startswith('## '):
                    preamble_lines.append(lines[i])
                    i += 1
                preamble_lines.append('\\end{abstract}\n')
                past_abstract = True
                continue
            elif line == '## References':
                body_lines.append('\\section*{References}\n\\small\n')
                bib_match = re.search(r'(\w+)\.bib', content)
                if bib_match:
                    body_lines.append(f'\\bibliographystyle{{unsrt}}\n\\bibliography{{{bib_match.group(1)}}}\n')
                i += 1
                continue
            elif line.startswith('### '):
                body_lines.append(f'\\subsection{{{line[4:].strip()}}}\n')
            elif line.startswith('## '):
                body_lines.append(f'\\section{{{line[3:].strip()}}}\n')
            else:
                body_lines.append(line)

            i += 1

    final = '\\documentclass{article}\n\n'
    final += '\n'.join(preamble_lines) + '\n\n'
    final += '\n'.join(body_lines) + '\n\n'
    final += '\\end{document}\n'
    Path(output_path).write_text(final)
    print(f'Created {output_path}')
def get_private_url(path: str):
    "Get the private URL for a file on the solveit cloud instance"
    server = os.getenv('PRIVATE_DOMAIN')
    if not server: raise ValueError("PRIVATE_DOMAIN not set")
    path = os.path.abspath(path)
    return f"https://{server}.solve.it.com{path.replace('/app/data', '/static')}"
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
