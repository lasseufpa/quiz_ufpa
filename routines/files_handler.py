from pathlib import Path
import os
import json

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
                print(f"!!! ERRO: O arquivo '{filename}' está mal formatado. Faltando 'title' ou 'questions'.")
                exit(1) # Sai do programa
            
            print(f"--- Quiz '{data['title']}' carregado com sucesso de '{filename}' ---")
            return data
            
    except FileNotFoundError:
        print(f"!!! ERRO: Arquivo do quiz '{filename}' não encontrado. !!!")
        print(f"Crie o arquivo '{filename}' no mesmo diretório do app.py.")
        exit(1) # Sai do programa
        
    except json.JSONDecodeError:
        print(f"!!! ERRO: O arquivo '{filename}' contém um JSON inválido. !!!")
        print("Use um validador de JSON online para verificar a sintaxe (aspas duplas, vírgulas, etc.).")
        exit(1) # Sai do programa


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