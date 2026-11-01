"""Configuração de logging da aplicação.

Os logs vão para o console **e** para um arquivo rotativo em `logs/server.log`.
Ao passar de 2 MB, o arquivo vira `server.log.1`, `server.log.2`, ... e os 5
mais recentes são mantidos.

Variáveis de ambiente:
    QUIZ_LOG_DIR    pasta dos logs (padrão: logs)
    QUIZ_LOG_LEVEL  nível mínimo: DEBUG, INFO, WARNING, ERROR (padrão: INFO)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = os.environ.get('QUIZ_LOG_DIR', 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'server.log')

LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

MAX_BYTES = 2 * 1024 * 1024   # 2 MB por arquivo
BACKUP_COUNT = 5              # server.log + server.log.1 ... .5


def setup_logging():
    """Configura o logger raiz com saída no console e em arquivo rotativo.

    Usar o logger raiz faz com que também sejam gravados os logs do Flask,
    do Werkzeug (requisições HTTP) e do Socket.IO/Engine.IO.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(os.environ.get('QUIZ_LOG_LEVEL', 'INFO').upper())

    # Evita handlers duplicados se a função for chamada mais de uma vez
    if any(getattr(handler, '_quiz_ufpa', False) for handler in root.handlers):
        return root

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console._quiz_ufpa = True

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    file_handler._quiz_ufpa = True

    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "Logs sendo gravados em %s", os.path.abspath(LOG_FILE)
    )
    return root


# Configura já na importação: os módulos registram mensagens durante o import.
setup_logging()

log = logging.getLogger(__name__)
