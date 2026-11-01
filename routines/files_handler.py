from pathlib import Path
import logging
import os
import json

from routines import logger  # noqa: F401  (configura o console + arquivo)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
QUIZZES_FOLDER =    'static/quizzes'   

def load_quiz_data(file):
    """Carrega as perguntas de um arquivo JSON."""
    filename = Path(__file__).parent /'..'/ 'static'/ 'quizzes' / (file + '.json')
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validação simples para garantir que o arquivo tem o formato esperado
            if 'title' not in data or 'questions' not in data:
                raise ValueError(
                    f"Quiz '{file}' mal formatado: faltando 'title' ou 'questions'."
                )
            
            log.info(f"--- Quiz '{data['title']}' carregado com sucesso de '{filename}' ---")
            return data
            
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Quiz '{file}' não encontrado. Crie o arquivo em static/quizzes."
        )

    except json.JSONDecodeError:
        raise ValueError(
            f"Quiz '{file}' contém um JSON inválido. "
            "Verifique a sintaxe (aspas duplas, vírgulas, etc.)."
        )


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_quiz_list():
    """Returns list of quiz names (without .json extension)"""
    quizzes = []
    for f in os.listdir(QUIZZES_FOLDER):
        if f.endswith('.json'):
            quizzes.append(f[:-5])
    return quizzes

def load_quiz(quiz_name):
    """Loads a quiz dict from quizzes/quiz_name.json"""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_quiz(quiz_name, data):
    """Saves quiz dict to quizzes/quiz_name.json"""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)