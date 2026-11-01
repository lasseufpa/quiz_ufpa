#!/bin/sh
# Prepara o ambiente e sobe o servidor.
# Executado automaticamente ao iniciar o container (ver Dockerfile).
set -e

# Pastas de dados. Quando são montadas como volume, já existem; quando não,
# criamos aqui para o app não reclamar.
mkdir -p .private scores static/quizzes static/quiz-figures static/graphs

if [ -s .private/.secret ]; then
    echo "--- Usando o .private/.secret já existente (ADMIN_PASSWORD é ignorado) ---"
else
    echo "--- Criando .private/.secret ---"
    python - <<'PY'
import hashlib
import os
import pathlib

flask_pw = os.environ.get('FLASK_PASSWORD', '').strip() or 'flask'
admin_pw = os.environ.get('ADMIN_PASSWORD', '').strip()
used_default = not admin_pw
admin_pw = admin_pw or 'admin'

path = pathlib.Path('.private/.secret')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    hashlib.sha256(flask_pw.encode('utf-8')).hexdigest() + '\n'
    + hashlib.sha256(admin_pw.encode('utf-8')).hexdigest() + '\n',
    encoding='utf-8',
)

if used_default:
    print('=' * 62)
    print('  ATENÇÃO: ADMIN_PASSWORD não foi definida.')
    print('  A senha do professor ficou sendo: admin')
    print('  Para trocar, reinicie com ADMIN_PASSWORD=suasenha')
    print('=' * 62)
else:
    print('--- Senha do professor definida via ADMIN_PASSWORD ---')
PY
fi

# exec: o Python passa a ser o processo principal do container (Ctrl+C funciona)
exec python app.py
