# Imagem do quiz_ufpa (Flask + Flask-SocketIO + matplotlib)
#
# Build:  docker build -t quiz-ufpa .
# Rodar:  docker compose up --build   (recomendado, ver docker-compose.yml)
FROM python:3.11-slim

# Logs sem buffer (aparecem na hora) e sem arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# As dependências entram primeiro para aproveitar o cache do Docker:
# mexer no código não reinstala o pip.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

EXPOSE 5000

# O script cria as pastas de dados e o .private/.secret (o app pediria a senha
# interativamente, o que não funciona em container).
ENTRYPOINT ["sh", "docker-entrypoint.sh"]
