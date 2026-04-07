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

### 3 - Inicie o servidor:

```sh
python app.py
```

## Como Iniciar:
Ao executar o código, aparecerá no terminal o IP ao qual o professor (admin) e aluno (usuário) devem logar.

```sh
Servidor Flask-Quiz iniciado!
Aponte seu navegador de host (professor) para: http://localhost:5000/host
Aponte seu navegador de admin para: http://localhost:5000/admin
Alunos devem acessar: http://10.10.20.163:5000
```

### Crie seus quizzes!
Use a interface em ``http://localhost:5000/editor`` para gerenciar seus próprios quizzes.

## Observações:
- O aluno apenas consegue logar se seu nome estiver cadastrado. O cadastro pode ser feito na tela do admin ou acessando diretamente o arquivo ``.private/users.json``.
- Formato para um ``.private/users.json``:
```json
[
  "nome único 1",
  "nome único 2"
]
```
- Ainda não há suporte para importar/exportar quizzes através da interface gráfica. Assim, para compartilhar seus quizzes, é necessário copiar os arquivos correspondentes em ``static/quizzes`` e ``static/quiz-figures``.
- Formato para as perguntas e respostas de um ``static/quizzes/Meu Quiz.json``:
```json
{
  "title": "Meu Quiz",
  "questions": [
    {
      "text": "Pergunta",
      "options": [
        "opção 0",
        "opção 1",
        "opção 2",
        "opção 3"
      ],
      "correct_option": 3,
      "figure": "nome_da_figura.png" // ou "none, se não houver"
    }
  ]
}
```
- O backend (ainda) não possui um banco de dados como SQL.