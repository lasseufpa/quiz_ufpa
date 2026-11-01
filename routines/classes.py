"""Turmas: cada turma tem sua própria lista de alunos e sua própria pasta de quizzes.

O cadastro fica em `.private/classes.json`:

    {
      "version": 1,
      "classes": {
        "<slug>": {"name": "Terapia 1B", "students": ["Ana", "Beto"]}
      }
    }

O `slug` é o identificador estável e também o nome da pasta
(`static/quizzes/<slug>/`). Ele é derivado do nome na criação e **nunca muda**
depois — renomear altera apenas o nome exibido, sem mexer nos arquivos.
"""

import logging
import os
import re
import shutil
import unicodedata

from routines import constants, json_store
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)

CLASSES_FILE = '.private/classes.json'
DEFAULT_CLASS_NAME = 'Turma padrão'
LEGACY_USERS_FILE = '.private/users.json'

# {slug: {'name': str, 'students': [str]}}
_classes = {}


# -------------------- Utilitários --------------------
def slugify(name):
    """Converte um nome livre em um slug seguro para nome de pasta."""
    text = unicodedata.normalize('NFKD', name or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-zA-Z0-9]+', '-', text).strip('-').lower()
    return text or 'turma'


def quiz_dir(class_slug):
    """Pasta com os quizzes de uma turma."""
    return os.path.join(constants.QUIZZES_FOLDER, class_slug)


def _unique_slug(name):
    """Gera um slug livre, acrescentando -2, -3... se necessário."""
    base = slugify(name)
    candidate = base
    counter = 2
    while candidate in _classes or os.path.isdir(quiz_dir(candidate)):
        candidate = f'{base}-{counter}'
        counter += 1
    return candidate


def _clean_students(students):
    """Normaliza a lista de alunos removendo vazios e duplicatas (case-insensitive)."""
    seen = {}
    for name in students or []:
        if not isinstance(name, str):
            continue
        name = name.strip()
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return list(seen.values())


# -------------------- Persistência --------------------
def load():
    """Carrega o cadastro de turmas do disco para a memória."""
    global _classes
    data, source = json_store.read_json(CLASSES_FILE)

    if not isinstance(data, dict) or not isinstance(data.get('classes'), dict):
        if source not in ('missing',):
            log.error(f"⚠️ {CLASSES_FILE} inválido e sem backup. Começando sem turmas.")
        _classes = {}
        return _classes

    loaded = {}
    for slug, info in data['classes'].items():
        if not isinstance(info, dict):
            continue
        name = str(info.get('name') or slug).strip() or slug
        loaded[slug] = {'name': name, 'students': _clean_students(info.get('students'))}

    _classes = loaded
    log.info(f"--- {len(_classes)} turma(s) carregada(s) de '{CLASSES_FILE}' ---")
    return _classes


def save():
    """Grava o cadastro de turmas (escrita atômica + backup)."""
    json_store.write_json(CLASSES_FILE, {'version': 1, 'classes': _classes})


# -------------------- Consultas --------------------
def all_classes():
    """Dicionário interno {slug: {'name', 'students'}}."""
    return _classes


def brief_list():
    """Lista enxuta para os seletores da interface."""
    return [
        {'slug': slug, 'name': info['name'], 'students': len(info['students'])}
        for slug, info in _classes.items()
    ]


def exists(class_slug):
    return class_slug in _classes


def get(class_slug):
    """Informação de uma turma (ou None)."""
    return _classes.get(class_slug)


def name_of(class_slug):
    """Nome exibido da turma (ou o próprio slug, se não existir)."""
    info = _classes.get(class_slug)
    return info['name'] if info else (class_slug or '')


def first_slug():
    """Slug da primeira turma cadastrada (ou None)."""
    return next(iter(_classes), None)


# -------------------- CRUD de turmas --------------------
def create(name):
    """Cria uma turma. Retorna (slug, erro)."""
    name = (name or '').strip()
    if not name:
        return None, 'O nome da turma não pode ser vazio.'

    if any(info['name'].lower() == name.lower() for info in _classes.values()):
        return None, f'Já existe uma turma chamada "{name}".'

    slug = _unique_slug(name)
    _classes[slug] = {'name': name, 'students': []}
    os.makedirs(quiz_dir(slug), exist_ok=True)
    save()
    log.info(f"Turma criada: {name} (slug: {slug})")
    return slug, None


def rename(class_slug, new_name):
    """Renomeia uma turma (o slug e a pasta não mudam). Retorna erro ou None."""
    new_name = (new_name or '').strip()
    if class_slug not in _classes:
        return 'Turma não encontrada.'
    if not new_name:
        return 'O nome da turma não pode ser vazio.'
    if any(s != class_slug and info['name'].lower() == new_name.lower()
           for s, info in _classes.items()):
        return f'Já existe uma turma chamada "{new_name}".'

    _classes[class_slug]['name'] = new_name
    save()
    log.info(f"Turma {class_slug} renomeada para {new_name}")
    return None


def delete(class_slug, remove_files=True):
    """Exclui uma turma e a pasta dos seus quizzes. Retorna erro ou None."""
    if class_slug not in _classes:
        return 'Turma não encontrada.'
    if len(_classes) == 1:
        return 'Não é possível excluir a única turma existente.'

    del _classes[class_slug]
    save()

    if remove_files:
        folder = quiz_dir(class_slug)
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)

    log.info(f"Turma excluída: {class_slug}")
    return None


# -------------------- CRUD de alunos --------------------
def students(class_slug):
    """Lista de alunos de uma turma."""
    info = _classes.get(class_slug)
    return list(info['students']) if info else []


def find_student(class_slug, nickname):
    """Retorna o nome canônico do aluno na turma, ou None se não estiver cadastrado."""
    if not nickname:
        return None
    nickname_lower = nickname.strip().lower()
    for name in students(class_slug):
        if name.lower() == nickname_lower:
            return name
    return None


def add_student(class_slug, nickname):
    """Adiciona um aluno. Retorna (nome_canonico, erro)."""
    info = _classes.get(class_slug)
    if info is None:
        return None, 'Turma não encontrada.'

    nickname = (nickname or '').strip()
    if not nickname:
        return None, 'O nome não pode ser vazio.'
    if find_student(class_slug, nickname) is not None:
        return None, f'O nome "{nickname}" (ou variação) já existe nesta turma.'

    info['students'] = _clean_students(info['students'] + [nickname])
    save()
    return nickname, None


def remove_student(class_slug, nickname):
    """Remove um aluno. Retorna (removido?, erro)."""
    info = _classes.get(class_slug)
    if info is None:
        return False, 'Turma não encontrada.'

    canonical = find_student(class_slug, nickname)
    if canonical is None:
        return False, 'Aluno não encontrado nesta turma.'

    info['students'] = [s for s in info['students'] if s != canonical]
    save()
    return True, None


def rename_student(class_slug, old_nickname, new_nickname):
    """Renomeia um aluno. Retorna (nome_novo, erro)."""
    info = _classes.get(class_slug)
    if info is None:
        return None, 'Turma não encontrada.'

    new_nickname = (new_nickname or '').strip()
    if not new_nickname:
        return None, 'O novo nome não pode ser vazio.'

    canonical = find_student(class_slug, old_nickname)
    if canonical is None:
        return None, 'Aluno original não encontrado nesta turma.'

    other = find_student(class_slug, new_nickname)
    if other is not None and other != canonical:
        return None, f'O nome "{new_nickname}" (ou variação) já existe nesta turma.'

    info['students'] = [new_nickname if s == canonical else s for s in info['students']]
    save()
    return new_nickname, None


# -------------------- Migração do modelo antigo --------------------
def _migrate_legacy_data(class_slug):
    """Move quizzes soltos em `static/quizzes/` para a turma e importa `users.json`."""
    root = constants.QUIZZES_FOLDER
    target = quiz_dir(class_slug)
    os.makedirs(target, exist_ok=True)

    moved = 0
    if os.path.isdir(root):
        for filename in sorted(os.listdir(root)):
            if not filename.endswith('.json'):
                continue
            # `users.json` e `classes.json` não ficam aqui, mas por segurança:
            if filename in ('users.json', 'classes.json'):
                continue
            src = os.path.join(root, filename)
            if not os.path.isfile(src):
                continue
            try:
                os.replace(src, os.path.join(target, filename))
                moved += 1
            except OSError as e:
                log.error(f"Não foi possível mover {filename} para a turma: {e}")

    legacy, _source = json_store.read_json(LEGACY_USERS_FILE)
    legacy_names = [n for n in legacy if isinstance(n, str)] if isinstance(legacy, list) else []
    if legacy_names:
        _classes[class_slug]['students'] = _clean_students(
            _classes[class_slug]['students'] + legacy_names
        )
    students_count = len(_classes[class_slug]['students'])

    save()
    if moved or students_count:
        log.info(
            f"Migração para a turma '{_classes[class_slug]['name']}': "
            f"{moved} quiz(zes) e {students_count} aluno(s)."
        )


def ensure_ready():
    """Garante que exista ao menos uma turma e migra dados do modelo antigo."""
    load()

    if not _classes:
        slug, error = create(DEFAULT_CLASS_NAME)
        if error:
            log.error(f"Não foi possível criar a turma padrão: {error}")
            return _classes
        _migrate_legacy_data(slug)
    else:
        # Garante que a pasta de cada turma exista
        for slug in _classes:
            os.makedirs(quiz_dir(slug), exist_ok=True)

    return _classes
