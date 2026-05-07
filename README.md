# Quiz UFPA

Aplicação de quiz em tempo real inspirada no Kahoot, com backend Node.js e frontend Next.js.

## Como executar

```sh
npm install
npm run dev
```

Abra no navegador:

```text
http://localhost:5000
http://localhost:5000/host
http://localhost:5000/host/login
http://localhost:5000/admin/login
http://localhost:5000/editor
```

## Login do host e do admin

O host e o admin usam a mesma senha. Se `ADMIN_PASSWORD` não estiver definido, o sistema cria `admin123` na primeira inicialização e grava o hash em `.private/config.json`.

O host precisa fazer login antes de abrir [app/host/page.jsx](app/host/page.jsx). Se o host desconectar, o estado do jogo fica salvo em `.private/game_save.json` e o próximo login pode retomar a partida.

## Dados persistidos

Os usuários autorizados ficam em `.private/users.json` como uma lista de nomes.

Exemplo:

```json
[
  "nome único 1",
  "nome único 2"
]
```

Os quizzes continuam armazenados em `static/quizzes/*.json`.

Exemplo de quiz:

```json
{
  "title": "Meu Quiz",
  "questions": [
    {
      "text": "Pergunta",
      "options": ["opção 0", "opção 1", "opção 2", "opção 3"],
      "correct_option": 3,
      "figure": "nome_da_figura.png"
    }
  ]
}
```

As imagens enviadas pelo editor são salvas em `static/quiz-figures/` e os gráficos de resposta são gerados em `static/graphs/`.

## Testes

```sh
npm run test:client
npm run test:server
npm run test:e2e
npm run test:load -- --url=http://localhost:5000/api/quizzes --total=200 --concurrency=20
```

- `test:client`: unitarios + componentes (React Testing Library + Jest).
- `test:server`: integracao de API, sockets e persistencia (Jest + Supertest + socket.io-client).
- `test:e2e`: fluxo completo no navegador (Playwright).
- `test:load`: carga simples no endpoint escolhido (Node.js + fetch).