# test_socketio_corrigido.py
import socketio
import threading
import time
import random
import json

ip = "10.10.20.125"

# Carregar nomes do arquivo users.json
def load_user_names():
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users_data = json.load(f)
            # Supondo que users.json é uma lista de nomes
            if isinstance(users_data, list):
                return users_data
            else:
                print("❌ Formato inválido do users.json. Esperado uma lista.")
                return []
    except FileNotFoundError:
        print("❌ Arquivo users.json não encontrado")
        return []
    except Exception as e:
        print(f"❌ Erro ao carregar users.json: {e}")
        return []

def test_player_connection(user_id, user_name):
    """Testa conexão Socket.IO com event handlers corrigidos"""
    try:
        # Cria cliente Socket.IO
        sio = socketio.Client(logger=False, engineio_logger=False)
        
        connected = False
        login_success = False
        questions_answered = 0
        
        @sio.event
        def connect():
            nonlocal connected
            connected = True
            print(f"✅ Usuário {user_id} ({user_name}): Conectado ao servidor")
            # Faz login imediatamente após conectar
            sio.emit('player_join', {'nickname': user_name, 'team': random.choice(["TIME A", "TIME B"])})
        
        @sio.event
        def connect_error(data):
            print(f"❌ Usuário {user_id} ({user_name}): Erro de conexão - {data}")
        
        @sio.event
        def disconnect():
            nonlocal connected
            connected = False
            print(f"⚠️ Usuário {user_id} ({user_name}): Desconectado")
        
        @sio.on('join_success')
        def on_join_success(data):
            nonlocal login_success
            login_success = True
            print(f"🎮 Usuário {user_id} ({user_name}): Login OK - Nickname: {data.get('nickname', '')}")
        
        @sio.on('join_failed')
        def on_join_failed(data):
            print(f"❌ Usuário {user_id} ({user_name}): Falha no login - {data.get('reason', '')}")
        
        @sio.on('show_question')
        def on_show_question(data):
            print(f"❓ Usuário {user_id} ({user_name}): Recebeu pergunta - {data.get('text', '')[:30]}...")
            # Responde aleatoriamente após 1-3 segundos
            options_count = len(data.get('options', []))
            if options_count > 0:
                time.sleep(random.uniform(1, 3))
                answer_index = random.randint(0, options_count - 1)
                sio.emit('submit_answer', {'option_index': answer_index})
                print(f"📝 Usuário {user_id} ({user_name}): Respondeu opção {answer_index}")
        
        @sio.on('answer_received')
        def on_answer_received(data):
            nonlocal questions_answered
            questions_answered += 1
            print(f"📨 Usuário {user_id} ({user_name}): Resposta confirmada")
        
        @sio.on('show_results')
        def on_show_results(data):
            score = data.get('scores', {}).get(sio.get_sid(), 0)
            print(f"📊 Usuário {user_id} ({user_name}): Resultados - Score: {score}")
        
        @sio.on('game_over')
        def on_game_over(data):
            print(f"🏁 Usuário {user_id} ({user_name}): Jogo finalizado")
        
        @sio.on('game_reset')
        def on_game_reset(data):
            print(f"🔄 Usuário {user_id} ({user_name}): Jogo reiniciado")
        
        # Conecta ao servidor
        print(f"🔗 Usuário {user_id} ({user_name}): Conectando...")
        sio.connect(f'http://{ip}:5000', wait_timeout=10)
        
        # Aguarda um pouco para ver se o login foi bem-sucedido
        time.sleep(2)
        
        if connected and login_success:
            print(f"🎯 Usuário {user_id} ({user_name}): Sessão ativa - Mantendo conexão por 45s")
            # Mantém a conexão por 45 segundos para capturar mais eventos
            time.sleep(45)
        else:
            print(f"⚠️ Usuário {user_id} ({user_name}): Conexão/login incompleto - Mantendo 15s")
            time.sleep(15)
        
        # Desconecta
        sio.disconnect()
        print(f"✅ Usuário {user_id} ({user_name}): Teste concluído - {questions_answered} perguntas respondidas")
        
    except Exception as e:
        print(f"❌ Usuário {user_id} ({user_name}): ERRO - {e}")

def test_simple_connection(user_id, user_name):
    """Teste mais simples apenas para verificar conexão básica"""
    try:
        sio = socketio.Client()
        
        @sio.event
        def connect():
            print(f"✅ {user_id} ({user_name}): Conectado!")
            sio.emit('player_join', {'nickname': user_name, 'team': "TIME A"})
        
        @sio.event
        def connect_error(data):
            print(f"❌ {user_id} ({user_name}): Erro conexão - {data}")
        
        @sio.on('join_success')
        def on_join_success(data):
            print(f"✅ {user_id} ({user_name}): Login confirmado")
        
        @sio.on('join_failed')
        def on_join_failed(data):
            print(f"❌ {user_id} ({user_name}): Falha no login - {data.get('reason', '')}")
        
        sio.connect(f'http://{ip}:5000', wait_timeout=10)
        print(f"✅ {user_id} ({user_name}): Handshake OK")
        
        # Mantém por 20 segundos
        time.sleep(20)
        
        sio.disconnect()
        print(f"✅ {user_id} ({user_name}): Conexão básica OK")
        
    except Exception as e:
        print(f"❌ {user_id} ({user_name}): FALHA - {e}")

# Teste principal
if __name__ == "__main__":
    print("🚀 INICIANDO TESTE DE CONEXÕES SOCKET.IO COM NOMES REAIS")
    print("=" * 50)
    
    # Carregar nomes de usuário
    user_names = load_user_names()
    
    if not user_names:
        print("❌ Nenhum nome de usuário carregado. Usando nomes padrão.")
        user_names = [f"Player_{i}" for i in range(40)]
    
    print(f"📊 Carregados {len(user_names)} nomes de usuário")
    print(f"📋 Primeiros 5 nomes: {user_names[:5]}")
    
    # Teste com número de conexões baseado na quantidade de nomes
    num_connections = min(len(user_names), 40)  # Máximo 40 conexões
    print(f"📊 Testando {num_connections} conexões simultâneas...")
    
    threads = []
    for i in range(num_connections):
        user_name = user_names[i] if i < len(user_names) else f"Player_{i}"
        t = threading.Thread(target=test_player_connection, args=(i, user_name))
        threads.append(t)
        t.start()
        time.sleep(0.15)  # Pequeno delay entre conexões
    
    # Aguarda todas as threads
    for t in threads:
        t.join()
    
    print("=" * 50)
    print("🎉 TESTE CONCLUÍDO!")