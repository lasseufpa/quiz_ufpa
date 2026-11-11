STATE_LOBBY 	= 0
STATE_QUESTION 	= 1
STATE_ANSWER 	= 2
STATE_GAMEOVER 	= 3
QUIZZES_FOLDER =    'static/quizzes'
UPLOAD_FOLDER =     'static/quiz-figures'
SECRET_FOLDER =     '.private'
SCORES_FOLDER =     'scores'
QUESTION_DURATION = 30

# --- Fase de resposta (tempo para escolher a alternativa) ---
# Cada pergunta pode definir o seu tempo em `answer_time` (segundos).
# Sem esse valor, o tempo é proporcional ao tamanho das alternativas.
ANSWER_CHARS_PER_SECOND = 3     # velocidade usada no cálculo automático
# Piso do cálculo automático: alternativas curtas (só números, "56 / 54 / 48") 
# não podem dar 2 s de resposta — o aluno ainda precisa resolver a conta.
ANSWER_MIN_DURATION = 10        # piso do cálculo automático (s)
ANSWER_MAX_DURATION = 120       # teto do cálculo automático (s)
ANSWER_MAX_EXPLICIT = 300       # teto para o valor definido no editor (s)

# --- Fase de leitura (entre exibir a pergunta e liberar as respostas) ---
# Cada pergunta pode definir o seu tempo em `reading_time` (segundos).
# Sem esse valor, o tempo é calculado pelo tamanho do enunciado.
READING_CHARS_PER_SECOND = 15   # velocidade de leitura usada no cálculo automático
READING_MIN_DURATION = 5        # piso do cálculo automático (s)
READING_MAX_DURATION = 60       # teto do cálculo automático (s)
READING_MAX_EXPLICIT = 300      # teto para o valor definido no editor (s)
READING_DURATION = 10           # legado: usado quando o enunciado não tem texto
GAME_SAVE_FILE = '.private/game_save.json'

# Sala (room do Socket.IO) dos participantes da partida (alunos + host).
# Eventos de jogo vão só para essa sala: quem ainda está na tela de entrada,
# digitando o nome, não recebe pergunta/resultados.
GAME_ROOM = 'partida'

# --- Modo time ---
# Ligado no apresentador antes de iniciar o quiz: cada aluno escolhe um dos
# times ao entrar e os resultados passam a mostrar o placar por time.
TEAM_MODE_DEFAULT = False
TEAM_KEYS = ('A', 'B')
TEAM_NAMES = {'A': 'Time A', 'B': 'Time B'}
TEAM_TOP_N = 2          # quantos jogadores de cada time aparecem nos resultados

# --- Pontuação de competição (bônus por rapidez) ---
# pts(t) = floor(COMPETITION_MAX_POINTS * sinc(t / COMPETITION_HALF_WINDOW) ^ EXP)
# com sinc(x) = sin(pi x) / (pi x). Vale o máximo em t = 0 e zera em 60 s.
# O guia do apresentador desenha essa curva a partir destes valores
# (ver routines/figures.py).
COMPETITION_MAX_POINTS = 200
COMPETITION_HALF_WINDOW = 60
COMPETITION_EXPONENT = 4
