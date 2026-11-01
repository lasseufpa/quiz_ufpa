#!/bin/sh
# Prepara o ambiente e sobe o servidor.
# Executado automaticamente ao iniciar o container (ver Dockerfile).
set -e

# Pastas de dados. Quando são montadas como volume, já existem; quando não,
# criamos aqui para o app não reclamar.
mkdir -p .private scores logs static/quizzes static/quiz-figures static/graphs

if [ -s .private/.secret ]; then
    echo "--- Senha do professor já configurada ---"
else
    echo "--- Primeira execução: defina a senha em http://localhost:5000/setup ---"
fi

# exec: o Python passa a ser o processo principal do container (Ctrl+C funciona)
exec python app.py
