"""Descoberta do endereço de rede usado para os alunos se conectarem."""

import os
import socket


def get_local_ip():
    # Permite forçar o IP mostrado aos alunos. Útil em Docker com portas
    # mapeadas, onde o IP detectado seria o interno do container.
    forced_ip = os.environ.get('QUIZ_HOST_IP')
    if forced_ip:
        return forced_ip

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip
