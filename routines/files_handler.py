from pathlib import Path
import logging
import os

from routines import json_store
from routines import logger  # noqa: F401  (configura o console + arquivo)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
QUIZZES_FOLDER =    'static/quizzes'   

def load_quiz_data(file):
    """Carrega as perguntas de um arquivo JSON (com recuperação de backup)."""
    filename = Path(__file__).parent / '..' / 'static' / 'quizzes' / (file + '.json')
    data, source = json_store.read_json(str(filename))

    if data is None:
        if source == 'missing':
            raise FileNotFoundError(
                f"Quiz '{file}' não encontrado. Crie o arquivo em static/quizzes."
            )
        raise ValueError(
            f"Quiz '{file}' está corrompido e não há backup válido."
        )

    if not isinstance(data, dict) or 'title' not in data or 'questions' not in data:
        raise ValueError(
            f"Quiz '{file}' mal formatado: faltando 'title' ou 'questions'."
        )

    log.info(f"--- Quiz '{data['title']}' carregado com sucesso de '{filename}' ---")
    return data


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
    """Carrega um quiz do disco (None se não existir)."""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    data, source = json_store.read_json(path)
    if data is None and source == 'missing':
        return None
    return data


def save_quiz(quiz_name, data):
    """Salva um quiz (escrita atômica + backup)."""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    json_store.write_json(path, data)