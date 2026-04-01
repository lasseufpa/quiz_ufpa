# ic_quiz

Uma ferramenta interativa inspirada no Kahoot, desenvolvida para dinamizar o aprendizado de conceitos de Inteligência Computacional.

## Passo a passo:
### 1 - Clone o repositório:

```sh
git clone https://github.com/Frank-Bruno/ic_kahoot.git
```

### 2 - Instalação de dependências:

```sh
pip install -r requirements.txt
```

### 3- Inicie o servidor:

```sh
python app.py
```

## Como Iniciar:
Ao executar o código aparecerá no terminal, o IP ao qual o professor (admin) e aluno (usuário) devem logar.

```sh
Servidor Flask-Quiz iniciado!
Aponte seu navegador de host (professor) para: http://localhost:5000/host
Aponte seu navegador de admin para: http://localhost:5000/admin
Alunos devem acessar: http://10.10.20.163:5000
```

## Observações:
- O aluno apenas consegue logar se seu nome estiver cadastrado. O cadastro pode ser feito na tela do admin ou acessando diretamente o arquivo users.json. (TODO: Pensar em um forma mais eficiente de fazer isso.)
- O dataset de questões é lido a partir do arquivo quiz.json.
