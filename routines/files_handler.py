"""Leitura e gravação dos quizzes, organizados por turma.

Layout em disco:

    static/quizzes/<slug-da-turma>/<nome-do-quiz>.json

O nome do arquivo é o identificador do quiz dentro da turma. Todos os acessos
passam por aqui para garantir escrita atômica e recuperação de backup.
"""

import logging
import os

from routines import classes, constants, json_store
from routines import logger  # noqa: F401  (configura o console + arquivo)

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def _validate_slug(class_slug):
    """Garante que o slug da turma é seguro para virar caminho de pasta."""
    if (not class_slug or '/' in class_slug or '\\' in class_slug
            or class_slug.startswith('.')):
        raise ValueError(f"Turma inválida: {class_slug!r}")
    if not classes.exists(class_slug):
        raise ValueError(f"Turma '{class_slug}' não existe.")
    return class_slug


def _validate_name(quiz_name):
    """Garante que o nome do quiz não escapa da pasta da turma."""
    if (not quiz_name or '/' in quiz_name or '\\' in quiz_name
            or quiz_name.startswith('.')):
        raise ValueError(f"Nome de quiz inválido: {quiz_name!r}")
    return quiz_name


def quiz_dir(class_slug):
    """Pasta dos quizzes de uma turma (criada se necessário)."""
    path = classes.quiz_dir(class_slug)
    os.makedirs(path, exist_ok=True)
    return path


def quiz_path(class_slug, quiz_name):
    """Caminho completo do arquivo de um quiz."""
    _validate_slug(class_slug)
    _validate_name(quiz_name)
    return os.path.join(quiz_dir(class_slug), f'{quiz_name}.json')


def load_quiz_data(class_slug, quiz_name):
    """Carrega as perguntas de um quiz da turma (com recuperação de backup)."""
    path = quiz_path(class_slug, quiz_name)
    data, source = json_store.read_json(path)

    if data is None:
        if source == 'missing':
            raise FileNotFoundError(
                f"Quiz '{quiz_name}' não encontrado na turma "
                f"'{classes.name_of(class_slug)}'."
            )
        raise ValueError(
            f"Quiz '{quiz_name}' está corrompido e não há backup válido."
        )

    if not isinstance(data, dict) or 'title' not in data or 'questions' not in data:
        raise ValueError(
            f"Quiz '{quiz_name}' mal formatado: faltando 'title' ou 'questions'."
        )

    log.info(f"--- Quiz '{data['title']}' carregado com sucesso de '{path}' ---")
    return data


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_quiz_list(class_slug):
    """Nomes dos quizzes de uma turma (sem a extensão .json)."""
    folder = quiz_dir(class_slug)
    return sorted(f[:-5] for f in os.listdir(folder) if f.endswith('.json'))


def list_quizzes_by_class():
    """{slug: [nomes]} — usado pelo "copiar de outra turma" do editor."""
    result = {}
    for slug in classes.all_classes():
        try:
            result[slug] = get_quiz_list(slug)
        except OSError as e:
            log.warning(f"Não foi possível listar os quizzes da turma {slug}: {e}")
            result[slug] = []
    return result


def load_quiz(class_slug, quiz_name):
    """Carrega um quiz do disco (None se não existir)."""
    path = quiz_path(class_slug, quiz_name)
    data, source = json_store.read_json(path)
    if data is None and source == 'missing':
        return None
    return data


def save_quiz(class_slug, quiz_name, data):
    """Salva um quiz (escrita atômica + backup)."""
    json_store.write_json(quiz_path(class_slug, quiz_name), data)


def delete_quiz(class_slug, quiz_name):
    """Exclui um quiz, seu backup e temporários. Retorna True se removeu algo."""
    path = quiz_path(class_slug, quiz_name)
    removed = False
    for suffix in ('', '.bak', '.tmp'):
        try:
            os.remove(path + suffix)
            removed = True
        except FileNotFoundError:
            pass
    return removed


def unique_quiz_name(class_slug, base_name):
    """Nome livre dentro da turma, acrescentando _1, _2... se já existir."""
    folder = quiz_dir(class_slug)
    name = base_name
    counter = 1
    while os.path.exists(os.path.join(folder, f'{name}.json')):
        name = f'{base_name}_{counter}'
        counter += 1
    return name


def copy_quiz(from_class, from_quiz, to_class, new_name=None):
    """Copia um quiz entre turmas. Retorna (nome_final, erro)."""
    if not classes.exists(from_class):
        return None, 'Turma de origem não encontrada.'
    if not classes.exists(to_class):
        return None, 'Turma de destino não encontrada.'

    try:
        data = load_quiz(from_class, from_quiz)
    except ValueError as e:
        return None, str(e)

    if data is None:
        return None, f"Quiz '{from_quiz}' não encontrado na turma de origem."

    base = (new_name or '').strip() or from_quiz
    base = ''.join(c if c.isalnum() or c in '.-_' else '_' for c in base).strip('_')
    if not base:
        base = from_quiz

    target_name = unique_quiz_name(to_class, base)
    save_quiz(to_class, target_name, data)
    log.info(
        f"Quiz '{from_quiz}' ({from_class}) copiado para "
        f"'{target_name}' ({to_class})."
    )
    return target_name, None


def absolute_quizzes_root():
    """Caminho absoluto da raiz das pastas de quizzes (para logs)."""
    return os.path.abspath(constants.QUIZZES_FOLDER)