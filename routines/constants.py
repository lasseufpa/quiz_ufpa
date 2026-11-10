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
ANSWER_CHARS_PER_SECOND = 10    # velocidade usada no cálculo automático
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
