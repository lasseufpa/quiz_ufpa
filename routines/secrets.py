"""Leitura e gravação do arquivo de segredos (`.private/.secret`).

O arquivo tem duas linhas:
    1) SECRET_KEY do Flask (gerado automaticamente)
    2) hash SHA-256 da senha do professor
"""

import os
from pathlib import Path

# Raiz do projeto (um nível acima de routines/)
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_PATH = BASE_DIR / '.private' / '.secret'


def read_secret_file(path=SECRET_PATH):
    """Retorna (secret_key, admin_hash), ou (None, None) se não configurado."""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return None, None

    secret_key = lines[0].strip() if len(lines) > 0 else ''
    admin_hash = lines[1].strip() if len(lines) > 1 else ''
    if not secret_key or not admin_hash:
        return None, None
    return secret_key, admin_hash


def write_secret_file(secret_key, admin_hash, path=SECRET_PATH):
    """Grava o arquivo atomicamente (tmp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + '.tmp')
    tmp_path.write_text(f"{secret_key}\n{admin_hash}\n", encoding='utf-8')
    os.replace(tmp_path, path)
