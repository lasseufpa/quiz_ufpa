"""Leitura e escrita de JSON com resistência a corrupção.

Cada arquivo tem uma versão de backup (`arquivo.json.bak`):

- **Escrita atômica**: grava em `arquivo.json.tmp`, `fsync` e troca com
  `os.replace`. Se o processo morrer no meio, o arquivo antigo continua íntegro.
- **Backup automático**: antes de trocar, a versão atual (se for JSON válido)
  é copiada para `arquivo.json.bak`.
- **Recuperação**: na leitura, se o principal estiver corrompido, o backup é
  usado e o principal é restaurado automaticamente.
"""

import json
import logging
import os

log = logging.getLogger(__name__)


def backup_path(path):
    """Caminho do backup de um arquivo JSON."""
    return f"{path}.bak"


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _atomic_write(path, data, indent=2):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def write_json(path, data, indent=2):
    """Grava o JSON atomicamente, mantendo a versão anterior em `.bak`."""
    if os.path.exists(path):
        try:
            previous = _load(path)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Não foi possível criar backup de %s: %s", path, e)
        else:
            try:
                _atomic_write(backup_path(path), previous, indent)
            except OSError as e:
                log.warning("Falha ao gravar o backup de %s: %s", path, e)

    _atomic_write(path, data, indent)


def read_json(path):
    """Lê o JSON, recuperando do backup se necessário.

    Retorna `(dados, origem)`, com origem em:
      - 'main'    → lido do arquivo principal;
      - 'backup'  → principal corrompido; backup usado e principal restaurado;
      - 'missing' → nenhum dos dois existe;
      - 'corrupt' → existe, mas nem o principal nem o backup são válidos.
    """
    if os.path.exists(path):
        try:
            return _load(path), 'main'
        except (OSError, json.JSONDecodeError) as e:
            log.error("Arquivo %s corrompido: %s", path, e)

    backup = backup_path(path)
    if os.path.exists(backup):
        try:
            data = _load(backup)
        except (OSError, json.JSONDecodeError) as e:
            log.error("Backup %s também está corrompido: %s", backup, e)
        else:
            log.warning("Recuperando %s a partir do backup.", path)
            try:
                _atomic_write(path, data)
            except OSError as e:
                log.error("Falha ao restaurar %s: %s", path, e)
            return data, 'backup'

    if not os.path.exists(path):
        return None, 'missing'
    return None, 'corrupt'
