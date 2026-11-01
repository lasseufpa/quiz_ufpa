import os
import json
import re

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
QUIZ_DIR = "quizzes"
FIG_DIR = "quiz-figures"
TEX_DIR = "tex"
MAIN_TEX = os.path.join(TEX_DIR, "main.tex")

# ----------------------------------------------------------------------
# Convert Unicode Greek letters and subscripts to LaTeX
# ----------------------------------------------------------------------
def unicode_to_latex(text):
    """Replace Unicode Greek letters, math symbols, and subscripts with LaTeX equivalents."""
    # Greek letters (unicode → LaTeX)
    greek = {
        'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
        'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
        'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
        'ν': r'\nu', 'ξ': r'\xi', 'ο': r'o', 'π': r'\pi ', 'ρ': r'\rho',
        'σ': r'\sigma ', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi',
        'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
        'Α': r'A', 'Β': r'B', 'Γ': r'\Gamma', 'Δ': r'\Delta',
        'Ε': r'E', 'Ζ': r'Z', 'Η': r'H', 'Θ': r'\Theta',
        'Ι': r'I', 'Κ': r'K', 'Λ': r'\Lambda', 'Μ': r'M',
        'Ν': r'N', 'Ξ': r'\Xi', 'Ο': r'O', 'Π': r'\Pi',
        'Ρ': r'P', 'Σ': r'\Sigma', 'Τ': r'T', 'Υ': r'\Upsilon',
        'Φ': r'\Phi', 'Χ': r'X', 'Ψ': r'\Psi', 'Ω': r'\Omega'
    }
    for uni, latex in greek.items():
        text = text.replace(uni, latex)
    
    # Additional math symbols
    math_symbols = {
        '∞': r'\infty',
        '≠': r'\neq',
        'ℓ': r'\ell',
        '≤': r'\le',
        '≥': r'\ge',
        '≈': r'\approx',
        '∑': r'\sum',
        '∫': r'\int',
        '√': r'\sqrt',
        '°': r'^\circ',          # degree symbol – must appear inside $...$ in text!
    }
    for uni, latex in math_symbols.items():
        text = text.replace(uni, latex)
    
    # Unicode subscripts (U+2080 to U+2089) → _{digit}
    sub_map = {
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'
    }
    for uni, digit in sub_map.items():
        if uni in text:
            text = text.replace(uni, f'_{digit}')
    return text

def fix_braces(text):
    """Fix malformed superscript/subscript braces, e.g., e^{{}-|k|} → e^{-|k|}"""
    text = re.sub(r'\{\{\}\}', '{}', text)
    text = re.sub(r'\{\}\s*(\^|_)', '', text)
    text = re.sub(r'\^\{(\{)?\}', '^', text)
    text = re.sub(r'\^\{(\{)([^}]+)(\})\}', r'^{\2}', text)
    return text

# ----------------------------------------------------------------------
# Light LaTeX escaping – only the mandatory special characters
# ----------------------------------------------------------------------
def escape_latex(s):
    """
    Convert Unicode math symbols, fix braces, and escape the few characters
    that are always special in LaTeX (&, %, #).  Backslashes (for LaTeX commands)
    and $, _, ^, ~ are left untouched; the user must provide proper $…$ around math.
    """
    s = unicode_to_latex(s)
    s = fix_braces(s)
    # Only escape characters that could accidentally break LaTeX outside math mode.
    s = s.replace('&', r'\&')
    s = s.replace('%', r'\%')
    s = s.replace('#', r'\#')
    return s

# ----------------------------------------------------------------------
# Generate a .tex file for a single quiz (always overwrite)
# ----------------------------------------------------------------------
def generate_quiz_tex(json_path, output_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    title = data.get("title", "Untitled Quiz")
    questions = data.get("questions", [])
    
    lines = []
    lines.append(r"\section*{" + escape_latex(title) + r"}")
    lines.append(r"\begin{enumerate}")
    
    for idx, q in enumerate(questions, start=1):
        # Question text: the JSON must already contain any needed $...$ around math.
        text = escape_latex(q.get("text", ""))
        options = q.get("options", [])
        figure = q.get("figure", "none")
        
        lines.append(rf"\item  {text}")
        
        if figure.lower() != "none":
            lines.append(r"\begin{center}")
            lines.append(rf"\includegraphics[width=0.7\linewidth]{{{figure}}}")
            lines.append(r"\end{center}")
        
        lines.append(r"\begin{enumerate}")
        for opt in options:
            # Options are taken verbatim after light escaping; math must be in $...$ by the user.
            lines.append(rf"\item {escape_latex(opt)}")
        lines.append(r"\end{enumerate}")
        lines.append(r"\vspace{0.5em}")
    
    lines.append(r"\end{enumerate}")
    lines.append(r"\newpage")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"Generated quiz: {output_path}")

# ----------------------------------------------------------------------
# Get current list of quizzes
# ----------------------------------------------------------------------
def get_current_quiz_list():
    if not os.path.isdir(QUIZ_DIR):
        return []
    json_files = [f for f in os.listdir(QUIZ_DIR) if f.endswith('.json')]
    return sorted([f[:-5] for f in json_files])

# ----------------------------------------------------------------------
# Generate main.tex from scratch
# ----------------------------------------------------------------------
def generate_main_tex(quiz_list, main_path):
    input_lines = [f"\\input{{{quiz}}}" for quiz in quiz_list]
    preamble = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{graphicx}",
        r"\usepackage{enumitem}",
        r"\usepackage{amsmath}",
        r"\usepackage{geometry}",
        r"\geometry{a4paper, margin=1in}",
        r"\graphicspath{{../quiz-figures/}}",
        r"",
        r"\title{Enquetes em Sala de Aula}",
        r"\author{Aldebaro Klautau\\Breno Silva}",
        r"",
        r"\begin{document}",
        r"\maketitle",
    ]
    with open(main_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(preamble + input_lines + [r"\input{gabarito}"]+[r"\end{document}"]))
    print(f"Generated {main_path}")

# ----------------------------------------------------------------------
# Generate answer key
# ----------------------------------------------------------------------
def generate_answer_key(quiz_dir, tex_dir, output_filename="gabarito.tex"):
    json_files = sorted([f for f in os.listdir(quiz_dir) if f.endswith('.json')])
    if not json_files:
        print("No quiz JSON files found.")
        return
    
    output_path = os.path.join(tex_dir, output_filename)
    lines = [r"\section*{Gabarito}", r"\renewcommand{\labelenumi}{\arabic{enumi}.}"]
    
    for json_file in json_files:
        quiz_name = json_file[:-5]
        with open(os.path.join(quiz_dir, json_file), 'r', encoding='utf-8') as f:
            data = json.load(f)
        title = data.get("title", quiz_name)
        questions = data.get("questions", [])
        
        lines.append(rf"\subsection*{{{escape_latex(title)}}}")
        lines.append(r"\begin{enumerate}")
        for idx, q in enumerate(questions, start=1):
            correct_idx = q.get("correct_option", -1)
            options = q.get("options", [])
            if 0 <= correct_idx < len(options):
                correct_text = escape_latex(options[correct_idx])
                letter = chr(ord('A') + correct_idx)
                lines.append(rf"\item  {letter}) {correct_text}")
            else:
                lines.append(rf"\item \textbf{{{idx}.}} (sem alternativa válida)")
        lines.append(r"\end{enumerate}")
        lines.append(r"\vspace{0.5cm}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"Generated answer key: {output_path}")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    os.makedirs(TEX_DIR, exist_ok=True)
    quiz_names = get_current_quiz_list()
    
    for quiz in quiz_names:
        json_file = os.path.join(QUIZ_DIR, f"{quiz}.json")
        tex_file = os.path.join(TEX_DIR, f"{quiz}.tex")
        if os.path.exists(json_file):
            generate_quiz_tex(json_file, tex_file)
    
    generate_main_tex(quiz_names, MAIN_TEX)
    generate_answer_key(QUIZ_DIR, TEX_DIR, "gabarito.tex")

if __name__ == "__main__":
    main()