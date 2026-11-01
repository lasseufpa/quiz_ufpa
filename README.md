# quiz_ufpa

Uma ferramenta interativa inspirada no Kahoot, desenvolvida para dinamizar o
aprendizado de conceitos de Inteligência Computacional e Processamento de Sinais.
O professor controla a partida em tempo real e os alunos respondem pelo celular
ou notebook, tudo pela rede local.

## Como iniciar

Você precisa ter o **Python 3** instalado. Clone o repositório e instale as
dependências:

```sh
git clone https://github.com/lasseufpa/quiz_ufpa.git
cd quiz_ufpa
pip install -r requirements.txt
```

Depois, inicie o servidor:

```sh
python app.py
```

Na **primeira execução**, o terminal pede duas senhas: uma de uso interno
(**FLASK**) e a senha do professor (**ADMIN**). Guarde a segunda — ela será
pedida para entrar na administração e na tela do apresentador.

Ao iniciar, o terminal mostra os endereços a usar:

```
Aponte seu navegador de host (professor) para: http://localhost:5000/host
Aponte seu navegador de admin para: http://localhost:5000/admin
Alunos devem acessar: http://10.10.20.163:5000
```

> O endereço dos alunos usa o IP da sua máquina na rede local — todos precisam
> estar na **mesma rede**.

## Rodar com Docker (sem instalar nada)

Se você só vai **usar** o sistema (não vai mexer no código), esta é a forma mais
fácil: não precisa instalar Python nem as dependências.

Você só precisa do [Docker](https://docs.docker.com/get-docker/) — no Windows e
no macOS, o Docker Desktop já vem com tudo.

Na pasta do projeto, execute:

```sh
ADMIN_PASSWORD=escolha-uma-senha docker compose up --build
```

Na primeira vez ele baixa e monta tudo (leva alguns minutos). Depois abra:

- **Apresentador:** `http://localhost:5000/host`
- **Administração:** `http://localhost:5000/admin`
- **Alunos:** o IP da sua máquina na rede local (aparece no terminal)

A senha de `ADMIN_PASSWORD` serve para o apresentador e para a administração.
Ela só é usada na **primeira execução**, quando as senhas são criadas.

**Para parar:** `Ctrl+C`. Para subir de novo depois: `docker compose up -d`.
Para encerrar de vez: `docker compose down`.

Seus dados ficam no computador, fora do container: quizzes, figuras, alunos,
senhas e os CSVs de resultado continuam lá mesmo se o container for apagado.

> **No macOS/Windows**, o `docker-compose.yml` usa `network_mode: host`, que
> funciona bem no Linux. Se os alunos não conseguirem abrir o endereço, troque
> essa linha por `ports: ["5000:5000"]` (há o exemplo comentado no arquivo).

**Para usar outra porta:** `QUIZ_PORT=8080 docker compose up`.

## As telas

| Tela | Endereço | Para quê serve |
|------|----------|----------------|
| **Aluno** | `http://<ip>:5000` | Informar o nome e responder às perguntas |
| **Apresentador** | `http://localhost:5000/host` | Conduzir a partida (pede senha) |
| **Administração** | `http://localhost:5000/admin` | Cadastrar os alunos (pede senha) |
| **Editor** | `http://localhost:5000/editor` | Criar e editar quizzes |

A senha do apresentador e da administração é a mesma (**ADMIN**).

## Como rodar uma partida

1. **Antes da aula:** cadastre os alunos na tela *Administração* e prepare o
   quiz na tela *Editor*.
2. Abra a tela do **Apresentador**, escolha o quiz e aguarde os alunos entrarem
   (a lista de quem chegou aparece na tela).
3. Os alunos abrem o endereço no celular ou notebook e digitam o nome
   cadastrado.
4. Clique em **Iniciar Jogo**. A cada pergunta, o apresentador vê quantos já
   responderam e clica em **Mostrar Resultados** para revelar a resposta certa,
   o gráfico e o pódio.
5. Clique em **Próxima Pergunta** para seguir. No fim, o placar aparece para
   todos.

## Cadastrar alunos

**Só entra quem estiver cadastrado.** Na tela *Administração*
(`http://localhost:5000/admin`, com a senha ADMIN):

- **Adicionar** — digite o nome e clique em *Adicionar*.
- **Editar** — clique em *Editar*, mude o nome e clique em *Salvar*.
- **Remover** — clique em *Remover* e confirme.

O cadastro é único e não diferencia maiúsculas de minúsculas (`Ana` e `ana` são
a mesma pessoa).

## Criar e editar quizzes

Abra a tela *Editor* (`http://localhost:5000/editor`). Tudo é feito pela
interface — não é preciso mexer em arquivos.

- **Novo** / **Excluir** — começar um quiz do zero ou apagar o selecionado.
- **+ Adicionar Pergunta** — cada pergunta tem um texto (aceita várias linhas),
  as alternativas e o botão de rádio que marca a **alternativa correta**.
- **Figura (opcional)** — escolha uma imagem do computador; ela aparece na
  pergunta para os alunos.
- **Salvar Quiz** — grave o quiz. Sem salvar, as mudanças são perdidas.

### Conferir antes da aula

Clique em **👁 Pré-visualizar** para ver exatamente o que o aluno verá:
pergunta, figura e alternativas, com a correta destacada. Use **← Anterior** /
**Próxima →** (ou as setas do teclado) para percorrer o quiz.

Cada pergunta também tem seu próprio botão **👁 Pré-visualizar**, que mostra só
ela.

### Compartilhar quizzes com outros professores

- **📤 Exportar Quiz** — salva o quiz em um único arquivo `.quiz` (com as figuras
  dentro), pronto para enviar por e-mail ou pendrive.
- **📂 Importar Quiz** — abre um arquivo `.quiz` recebido. Se já existir um quiz
  com o mesmo nome, é criada uma cópia, sem sobrescrever o seu.

### Escrever fórmulas matemáticas

Nos textos das perguntas e das alternativas, escreva as fórmulas entre cifrões:
`$x[n]$` aparece no meio da linha e `$$\int x(t)\,dt$$` aparece centralizada.

Quem transforma isso em fórmula bonita é o **MathJax**. Por padrão ele é buscado
na internet (CDN). **Se a sala não tiver internet, baixe uma cópia uma única vez**
(precisa do [Node.js](https://nodejs.org) instalado):

```sh
npm install mathjax@4
mkdir -p static/mathjax static/@mathjax
cp -r node_modules/mathjax/* static/mathjax/
cp -r node_modules/@mathjax/mathjax-newcm-font static/@mathjax/
```

Com as pastas `static/mathjax/` e `static/@mathjax/` no lugar, as fórmulas passam
a funcionar **offline**: a página usa a cópia local e só recorre à internet se
ela não existir.

> As fontes ficam em um pacote separado (`@mathjax/mathjax-newcm-font`), por isso
> são duas pastas. Nenhuma delas fica salva no repositório, então cada computador
> que for rodar o sistema sem internet precisa baixá-las uma vez. Depois de
> copiar, o `node_modules/` pode ser apagado.

## Pontuação e resultados

Cada jogador acumula **duas notas** ao mesmo tempo:

- **Avaliação** — 1 ponto por acerto. Serve para medir quem aprendeu.
- **Competição** — pontos extras por acerto **rápido**: acertar primeiro vale
  mais (até 200 pontos por pergunta). Quem erra não pontua.

Em cada pergunta, clique em **Mostrar Resultados** para revelar:

- a alternativa correta;
- um gráfico com a **distribuição das respostas** e o **pódio** (os 3 melhores
  da pergunta);
- o botão **📋 Mostrar Pergunta Novamente**, para reler a pergunta com a turma.

No fim do quiz — ou ao clicar em **Finalizar Quiz** — todos veem o placar final,
e um arquivo CSV com as notas é gravado automaticamente na pasta `scores/`,
pronto para levar as notas de participação para a planilha.

## Se algo der errado

- **Recarreguei a página e "perdi" o jogo.** Não perdeu: quem recarrega volta
  para onde estava, mantendo pontos e respostas. Se o apresentador cair, a
  partida fica pausada até ele voltar.
- **O aluno não consegue entrar.** Confira se o nome dele está cadastrado na
  tela *Administração* e se foi digitado igual ao cadastro.
- **Os alunos não abrem o endereço.** Todos precisam estar na mesma rede do seu
  computador, e o aluno deve usar o IP que aparece no terminal (nunca
  `localhost`).
- **Esqueci a senha do professor.** Apague o arquivo `.private/.secret` e inicie
  o servidor de novo para criar outras senhas. No Docker, apague o arquivo e
  rode `ADMIN_PASSWORD=nova-senha docker compose up --build`.
- **Quero recomeçar uma partida.** Use o botão **Finalizar Quiz** na tela do
  apresentador e inicie um novo jogo.
- **As fórmulas aparecem como texto (`$x[n]$`).** O MathJax não carregou — em
  geral é falta de internet. Baixe a cópia local indicada em
  *Escrever fórmulas matemáticas*.

## Gerar a prova impressa (opcional)

Dá para transformar os quizzes em uma folha de prova com gabarito. No terminal:

```sh
cd static
python texify.py
```

Os arquivos são gerados em `static/tex/`. Para virar PDF, é preciso ter o LaTeX
instalado na máquina.