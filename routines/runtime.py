"""Estado mutável compartilhado entre os módulos da aplicação.

Fica em um módulo separado para que `app.py` seja só o bootstrap e para evitar
import circular entre rotas, eventos de socket e persistência.

Sempre acesse via `runtime.<nome>` (nunca `from routines.runtime import ...`),
porque alguns valores são reatribuídos durante a execução.
"""

from routines import game_state_handler as game_handler

# Estado da partida (mutado in-place na maioria das operações)
game_state = game_handler.clear_game_state()

# Quiz carregado no momento (definido ao iniciar a partida)
quiz_data = None

# Hash da senha do professor ('' enquanto não configurada)
admin_password = ''

# True na primeira execução, até a senha ser definida em /setup
setup_required = True

# Instância do SocketIO (definida pelo bootstrap; usada pelos handlers)
socketio = None
