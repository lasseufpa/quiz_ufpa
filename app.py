import os
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json

import csv
from datetime import datetime
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import socket
import getpass

import hashlib
import time

from werkzeug.utils import secure_filename
from flask import send_from_directory


PLAYER_SESSIONS = {}  # {session_token: {'sid': sid, 'nickname': nickname}}

STATE_LOBBY 	= 0
STATE_QUESTION 	= 1
STATE_ANSWER 	= 2
STATE_GAMEOVER 	= 3


from pathlib import Path
import hashlib

# Configuration
QUIZZES_FOLDER =    'static/quizzes'          # stores quizname.json files
UPLOAD_FOLDER =     'static/quiz-figures'           # stores quiz figures
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create folders if they don't exist
os.makedirs(QUIZZES_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


secretpath = Path(__file__).parent /".private" /".secret"

def promptPassword(name):
    string = getpass.getpass(f'Create {name} password: ')
    encoded_string = string.encode('utf-8')
    hash_object = hashlib.sha256(encoded_string)
    hex_digest = hash_object.hexdigest()
    return hex_digest


if not secretpath.exists():
    with open(secretpath, 'w+') as file:
        file.write(''+promptPassword('FLASK') +'\n')
        file.write(''+promptPassword('ADMIN') +'\n')
else:
    with open(secretpath, 'r+') as file:
        numlines = len(file.readlines())
        if numlines == 0:
            file.write(''+promptPassword('FLASK') +'\n')
            file.write(''+promptPassword('ADMIN') +'\n')
        elif numlines == 1:
            file.write(''+promptPassword('ADMIN') +'\n')
        elif numlines > 2:
            print("arquivo .secret inválido")
            exit()


        
app = Flask(__name__)
with open(secretpath, 'r+') as file:
    app.config['SECRET_KEY']    = file.readline().strip()
    ADMIN_PASSWORD              = file.readline().strip()

socketio = SocketIO(
    app,
    async_mode='eventlet',  # FORÇA usar eventlet
    logger=False,           # Desativa logs em produção
    engineio_logger=False,  # Desativa logs do engineio
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e7  # 10MB
)

def export_scores_to_csv(scores, players):
    """Exporta os resultados do quiz para um arquivo CSV local."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scores/scores_{timestamp}.csv"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Jogador', 'Pontuação'])
        for sid, score in scores.items():
            writer.writerow([players.get(sid, 'Desconhecido'), score])

    print(f"✅ Resultados exportados para {filename}")



# --- Nosso "Banco de Dados" de Perguntas ---
def load_quiz_data(file):
    """Carrega as perguntas de um arquivo JSON."""
    filename = Path(__file__).parent / 'static'/ 'quizzes' / (file + '.json')
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validação simples para garantir que o arquivo tem o formato esperado
            if 'title' not in data or 'questions' not in data:
                print(f"!!! ERRO: O arquivo '{filename}' está mal formatado. Faltando 'title' ou 'questions'.")
                exit(1) # Sai do programa
            
            print(f"--- Quiz '{data['title']}' carregado com sucesso de '{filename}' ---")
            return data
            
    except FileNotFoundError:
        print(f"!!! ERRO: Arquivo do quiz '{filename}' não encontrado. !!!")
        print(f"Crie o arquivo '{filename}' no mesmo diretório do app.py.")
        exit(1) # Sai do programa
        
    except json.JSONDecodeError:
        print(f"!!! ERRO: O arquivo '{filename}' contém um JSON inválido. !!!")
        print("Use um validador de JSON online para verificar a sintaxe (aspas duplas, vírgulas, etc.).")
        exit(1) # Sai do programa

# --- Nosso "Banco de Dados" de Perguntas (Agora carregado do arquivo) ---
QUIZ_DATA = None


# ### INÍCIO BLOCO MODIFICADO: Gerenciamento de Usuários ###
USERS_FILE = '.private/users.json'

def load_users(filename=USERS_FILE):
    """Carrega a lista de usuários do JSON. Retorna um DICIONÁRIO {lower: canonical}."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list) or not all(isinstance(s, str) for s in data):
                print(f"Aviso: {filename} mal formatado. Tratando como lista vazia.")
                return {} # ### MUDANÇA ### Retorna dict vazio
            
            # ### MUDANÇA ### Cria um dicionário {nome_minusculo: NomeOriginal}
            return {user.lower(): user for user in data}
            
    except FileNotFoundError:
        print(f"Aviso: {filename} não encontrado. Criando um novo.")
        save_users({}) # ### MUDANÇA ### Salva dict vazio
        return {} # ### MUDANÇA ### Retorna dict vazio
    except json.JSONDecodeError:
        print(f"Aviso: {filename} inválido. Tratando como lista vazia.")
        return {} # ### MUDANÇA ### Retorna dict vazio

def save_users(users_dict, filename=USERS_FILE):
    """Salva o DICIONÁRIO de usuários de volta no JSON (apenas os nomes originais)."""
    # ### MUDANÇA ### Extrai apenas os valores (nomes originais) para salvar
    canonical_names = list(users_dict.values())
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(canonical_names, f, indent=2, ensure_ascii=False)

# Carrega os usuários na inicialização
REGISTERED_USERS = load_users() # ### MUDANÇA ### Agora é um dict
print(f"--- {len(REGISTERED_USERS)} usuários carregados de '{USERS_FILE}' ---")
# ### FIM BLOCO MODIFICADO ###


# --- Estado do Jogo (Sem mudanças) ---
game_state = {
    'host_sid': None,
    'players': {}, # Dicionário de {sid: 'nickname'}
    'current_question': -1, # -1 = Lobby, 0 = Pergunta 1, etc.
    'answers': {}, # Dicionário de {sid: option_index}
    'scores': {}, # Dicionário de {sid: score}
    'state': {0}    # lobby = 0, pergunta = 1, resposta = 2, gameover = 3 
}

# --- Rotas HTTP (Modificadas para incluir Admin) ---

def generate_session_token():
    """Gera um token único para a sessão do jogador."""
    import secrets
    return secrets.token_hex(16)

@app.route('/')
def player_join():
    return render_template('player.html')

@app.route('/host')
def host_view():
    local_ip = get_local_ip()
    return render_template('host.html', 
                           quiz_title="Quiz UFPA", 
                           host_ip=local_ip)

@app.route('/check_session')
def check_session():
    """Verifica se existe uma sessão válida para o token fornecido."""
    token = request.args.get('token')
    
    if token in PLAYER_SESSIONS:
        session_data = PLAYER_SESSIONS[token]
        # Verifica se o jogador ainda está no jogo
        if session_data['sid'] in game_state['players']:
            return jsonify({
                'valid': True,
                'nickname': session_data['nickname']
            })
    return jsonify({'valid': False})

@socketio.on('restore_session')
def on_restore_session(data):
    """Tenta restaurar a sessão de um jogador após recarregar a página."""
    token = data.get('token')
    new_sid = data.get('new_sid')
    
    if token in PLAYER_SESSIONS:
        session_data = PLAYER_SESSIONS[token]
        old_sid = session_data['sid']
        nickname = session_data['nickname']
        
        # Verifica se o jogador ainda está no jogo
        if old_sid in game_state['players']:
            # Atualiza o SID para o novo
            game_state['players'][new_sid] = game_state['players'].pop(old_sid)
            game_state['scores'][new_sid] = game_state['scores'].pop(old_sid, 0)
            
            # Se tinha uma resposta, transfere também
            if old_sid in game_state['answers']:
                game_state['answers'][new_sid] = game_state['answers'].pop(old_sid)
            
            # Atualiza o token com o novo SID
            PLAYER_SESSIONS[token]['sid'] = new_sid
            
            # Notifica o jogador
            emit('session_restored', {
                'nickname': nickname,
                'current_question': game_state['current_question'],
                'current_score': game_state['scores'].get(new_sid, 0),
                'options': [0,1,2,3],
                'state': game_state['state']
            }, to=new_sid)
            
            # Atualiza o host
            if game_state['host_sid']:
                emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])
            
            print(f"Sessão restaurada para {nickname}. Novo SID: {new_sid}")
            return
    
    # Se não encontrou sessão válida
    emit('session_restore_failed', {'reason': 'Sessão não encontrada ou expirada'}, to=new_sid)

# ### INÍCIO BLOCO NOVAS ROTAS ADMIN
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login do admin."""
    if request.method == 'POST':
        password = request.form.get('password')
        encoded_string = password.encode('utf-8')
        hash_object = hashlib.sha256(encoded_string)
        password = hash_object.hexdigest().strip()

        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            print("Login de admin bem-sucedido.")
            return redirect(url_for('admin_view'))
        else:
            flash('Senha incorreta!', 'error')
            print("Tentativa de login de admin falhou.")
    return render_template('admin_login.html')

@app.route('/admin')
def admin_view():
    """Página de gerenciamento (agora protegida)."""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html')
    
@app.route('/admin/logout')
def admin_logout():
    """Remove o admin da sessão."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# --- Eventos WebSocket ---

@socketio.on('connect')
def on_connect():
    print(f"Cliente conectado: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"Cliente desconectado: {request.sid}")
    
    if request.sid == game_state['host_sid']:
        print("!!! O ANFITRIÃO DESCONECTOU. RESETANDO O JOGO. !!!")
        game_state.update(host_sid=None, players={}, current_question=-1, answers={}, scores={})
        PLAYER_SESSIONS.clear()  # Limpa todas as sessões
        emit('game_reset', broadcast=True)
    elif request.sid in game_state['players']:
        nickname = game_state['players'].get(request.sid, '??')
        if game_state['host_sid']:
            emit('player_left', {'nickname': nickname}, to=game_state['host_sid'])
        print(f"Jogador {nickname} saiu.")

@socketio.on('host_join')
def on_host_join():
    game_state['host_sid'] = request.sid
    print(f"Anfitrião se juntou: {request.sid}")
    emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])

# ### INÍCIO EVENTOS ADMIN (Modificados) ###
@socketio.on('admin_join')
def on_admin_join():
    """Admin se conectou à página de gerenciamento."""
    if not session.get('admin_logged_in'): return # Proteção
    
    print(f"Admin se conectou: {request.sid}")
    # ### MUDANÇA ### Envia os valores (nomes originais) do dict
    emit('update_user_list', sorted(list(REGISTERED_USERS.values())), to=request.sid)

@socketio.on('add_user')
def on_add_user(data):
    """Admin adicionou um novo usuário."""
    if not session.get('admin_logged_in'): return # Proteção

    nickname = data.get('nickname', '').strip()
    nickname_lower = nickname.lower() # ### MUDANÇA ###
    
    # ### MUDANÇA ### Verifica a chave (minúscula)
    if nickname and nickname_lower not in REGISTERED_USERS:
        REGISTERED_USERS[nickname_lower] = nickname # ### MUDANÇA ### Adiciona ao dict
        save_users(REGISTERED_USERS)
        print(f"Admin adicionou usuário: {nickname}")
        # ### MUDANÇA ### Envia os valores (nomes originais)
        emit('update_user_list', sorted(list(REGISTERED_USERS.values())), broadcast=True)
    elif nickname_lower in REGISTERED_USERS:
         emit('admin_error', {'message': f'O nome "{nickname}" (ou variação) já existe.'}, to=request.sid)


@socketio.on('remove_user')
def on_remove_user(data):
    """Admin removeu um usuário."""
    if not session.get('admin_logged_in'): return # Proteção

    nickname = data.get('nickname')
    nickname_lower = nickname.lower() # ### MUDANÇA ###
    
    # ### MUDANÇA ### Procura a chave (minúscula) e remove
    if nickname_lower in REGISTERED_USERS:
        del REGISTERED_USERS[nickname_lower] # ### MUDANÇA ###
        save_users(REGISTERED_USERS)
        print(f"Admin removeu usuário: {nickname}")
        # ### MUDANÇA ### Envia os valores (nomes originais)
        emit('update_user_list', sorted(list(REGISTERED_USERS.values())), broadcast=True)

@socketio.on('edit_user')
def on_edit_user(data):
    """Admin editou o nome de um usuário."""
    if not session.get('admin_logged_in'): return # Proteção

    old_nickname = data.get('old_nickname')
    new_nickname = data.get('new_nickname', '').strip()

    if not old_nickname or not new_nickname:
        emit('admin_error', {'message': 'O novo nome não pode ser vazio.'}, to=request.sid)
        return

    # ### MUDANÇA ### Converte tudo para minúsculo para verificação
    old_lower = old_nickname.lower()
    new_lower = new_nickname.lower()

    if old_lower not in REGISTERED_USERS:
        emit('admin_error', {'message': 'Usuário original não encontrado.'}, to=request.sid)
        return

    if new_lower in REGISTERED_USERS and new_lower != old_lower:
        emit('admin_error', {'message': f'O nome "{new_nickname}" (ou variação) já existe.'}, to=request.sid)
        return
        
    # ### MUDANÇA ### Executa a alteração no dict
    del REGISTERED_USERS[old_lower]
    REGISTERED_USERS[new_lower] = new_nickname
    save_users(REGISTERED_USERS)
    
    print(f"Admin editou usuário: de '{old_nickname}' para '{new_nickname}'")
    # ### MUDANÇA ### Envia os valores (nomes originais)
    emit('update_user_list', sorted(list(REGISTERED_USERS.values())), broadcast=True)
# ### FIM EVENTOS ADMIN ###


# ### MODIFICADO: on_player_join ###
@socketio.on('player_join')
def on_player_join(data):
    """Um aluno (player) tentou entrar no jogo."""
    nickname = data.get('nickname', '').strip()
    
    if not nickname:
        return

    # --- INÍCIO DA NOVA LÓGICA DE VALIDAÇÃO (CASE-INSENSITIVE) ---
    nickname_lower = nickname.lower() # ### MUDANÇA ###
    

    if nickname_lower not in REGISTERED_USERS:
        emit('join_failed', {'reason': 'Usuário não cadastrado. Fale com o administrador.'}, to=request.sid)
        print(f"Falha no login: Usuário '{nickname}' não cadastrado.")
        return

    # ### MUDANÇA ### Pega o nome "correto" (ex: "Frank") do dict
    canonical_name = REGISTERED_USERS[nickname_lower] 

    # ### MUDANÇA ### Verifica se o nome "correto" já está na lista de valores
    if canonical_name in game_state['players'].values():
        emit('join_failed', {'reason': 'Este usuário já está no jogo.'}, to=request.sid)
        print(f"Falha no login: Usuário '{canonical_name}' já está no jogo.")
        return
    # --- FIM DA NOVA LÓGICA DE VALIDAÇÃO ---

    print(f"Jogador {canonical_name} (autorizado) entrou.")
    game_state['players'][request.sid] = canonical_name # ### MUDANÇA ### Salva o nome "correto"
    game_state['scores'][request.sid] = 0

    # Criar token de sessão
    session_token = generate_session_token()
    PLAYER_SESSIONS[session_token] = {
        'sid': request.sid,
        'nickname': canonical_name
    }
    
    if game_state['host_sid']:
        emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])
    
    emit('join_success', 
         {
             'nickname': canonical_name,
            'session_token': session_token
        },
        to=request.sid)


@socketio.on('start_game')
def on_start_game(data):
    if request.sid != game_state['host_sid']:
        return
    quiz = data.get('quiz-name')
    global QUIZ_DATA
    QUIZ_DATA = load_quiz_data(quiz)
    print("Iniciando o jogo!")
    advance_question()

@socketio.on('next_question')
def on_next_question():
    if request.sid != game_state['host_sid']:
        return
    advance_question()

def advance_question():
    game_state['answers'] = {} 
    game_state['current_question'] += 1
    game_state['state'] = STATE_QUESTION
    q_index = game_state['current_question']

    if q_index >= len(QUIZ_DATA['questions']):
        print("Fim do quiz.")
        leaderboard = []
        for sid, nickname in game_state['players'].items():
            leaderboard.append({
                'nickname': nickname,
                'score': game_state['scores'].get(sid, 0)
            })
        leaderboard.sort(key=lambda x: x['score'], reverse=True)
        export_scores_to_csv(game_state['scores'], game_state['players'])
        emit('game_over', leaderboard, broadcast=True)
        game_state['state'] = STATE_GAMEOVER
    else:
        question_data = QUIZ_DATA['questions'][q_index]
        figure = question_data['figure']
        chart_path = ""
        if figure != "none":
            chart_path = f"{UPLOAD_FOLDER}/{figure}"
        payload = {
            'text': question_data['text'],
            'options': question_data['options'],
            'question_index': q_index,
            'total_questions': len(QUIZ_DATA['questions']),
            'chart_path': chart_path
        }
        emit('show_question', payload, broadcast=True)
        if game_state['host_sid']:
            emit('update_answer_count', {
                'answered': 0, 
                'total': len(game_state['players'])
            }, to=game_state['host_sid'])

@socketio.on('submit_answer')
def on_submit_answer(data):
    if request.sid not in game_state['players']:
        return 
    option_index = data.get('option_index')
    game_state['answers'][request.sid] = option_index
    print(f"Jogador {game_state['players'][request.sid]} respondeu: {option_index}")
    emit('answer_received', to=request.sid)
    if game_state['host_sid']:
        emit('update_answer_count', {
            'answered': len(game_state['answers']), 
            'total': len(game_state['players'])
        }, to=game_state['host_sid'])

def save_answer_distribution_chart(answer_distribution, question_data, question_index):
    os.makedirs('static/graphs', exist_ok=True)
    labels = ['A', 'B', 'C', 'D'][:len(answer_distribution)]
    values = answer_distribution
    plt.figure(figsize=(5,3))
    plt.bar(labels, values, color=['#007bff', '#28a745', '#ffc107', '#dc3545'][:len(values)])
    plt.title(f"Distribuição das respostas - Pergunta {question_index + 1}")
    plt.xlabel("Alternativas")
    plt.ylabel("Número de respostas")
    plt.tight_layout()
    filename = f"static/graphs/q{question_index + 1}_results.png"
    plt.savefig(filename)
    plt.close()
    return filename

@socketio.on('show_results')
def on_show_results():
    if request.sid != game_state['host_sid']:
        return
    q_index = game_state['current_question']
    if q_index < 0 or q_index >= len(QUIZ_DATA['questions']):
        return
    question_data = QUIZ_DATA['questions'][q_index]
    correct_option_index = question_data['correct_option']
    correct_option_text = question_data['options'][correct_option_index] 
    answer_distribution = [0] * len(question_data['options'])
    for ans in game_state['answers'].values():
        try:
            answer_distribution[int(ans)] += 1
        except (ValueError, TypeError, IndexError):
            pass

    for sid, answer in game_state['answers'].items():
        try:
            if int(answer) == int(correct_option_index):
                game_state['scores'][sid] = game_state['scores'].get(sid, 0) + 10
        except:
            pass
    chart_path = save_answer_distribution_chart(answer_distribution, question_data,q_index)
    payload = {
    'correct_option': correct_option_index,
    'correct_option_text': chr(ord('A')+correct_option_index) + ') ' + correct_option_text,
    'scores': game_state['scores'],
    'players': game_state['players'],
    'answer_distribution': answer_distribution,
    'chart_path': chart_path
    }
    emit('show_results', payload, broadcast=True)
    print("Mostrando resultados.")
    game_state['state'] = STATE_ANSWER

@socketio.on('force_end_quiz')
def on_force_end_quiz():
    if request.sid != game_state['host_sid']:
        return 
    print("Quiz finalizado forçadamente pelo host")
    leaderboard = []
    for sid, nickname in game_state['players'].items():
        leaderboard.append({
            'nickname': nickname,
            'score': game_state['scores'].get(sid, 0)
        })
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    export_scores_to_csv(game_state['scores'], game_state['players'])
    emit('game_over', leaderboard, broadcast=True)
    game_state['state'] = STATE_GAMEOVER
    game_state['current_question'] = -1
    game_state['answers'] = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_quiz_list():
    """Returns list of quiz names (without .json extension)"""
    quizzes = []
    for f in os.listdir(QUIZZES_FOLDER):
        if f.endswith('.json'):
            quizzes.append(f[:-5])
    return quizzes

def load_quiz(quiz_name):
    """Loads a quiz dict from quizzes/quiz_name.json"""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_quiz(quiz_name, data):
    """Saves quiz dict to quizzes/quiz_name.json"""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# -------------------- Routes --------------------
@app.route('/editor')
def editor_view():
    """Página de gerenciamento de quizzes."""
    return render_template('editor.html')


@app.route('/api/quizzes', methods=['GET'])
def api_list_quizzes():
    """Return list of available quiz names"""
    return jsonify(get_quiz_list())

@app.route('/api/quiz/<quiz_name>', methods=['GET'])
def api_get_quiz(quiz_name):
    """Return a single quiz JSON"""
    quiz = load_quiz(quiz_name)
    if quiz is None:
        return jsonify({'error': 'Quiz not found'}), 404
    return jsonify(quiz)

@app.route('/api/quiz/<quiz_name>', methods=['POST'])
def api_save_quiz(quiz_name):
    """Create or update a quiz. Expects JSON body with title and questions."""
    data = request.get_json()
    if not data or 'title' not in data or 'questions' not in data:
        return jsonify({'error': 'Invalid quiz data'}), 400
    
    # Optional: validate structure
    save_quiz(quiz_name, data)
    return jsonify({'message': 'Quiz saved successfully'})

@app.route('/api/quiz/<quiz_name>', methods=['DELETE'])
def api_delete_quiz(quiz_name):
    """Delete a quiz file"""
    path = os.path.join(QUIZZES_FOLDER, f'{quiz_name}.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Quiz not found'}), 404
    os.remove(path)
    return jsonify({'message': 'Quiz deleted'})

@app.route('/api/upload_image', methods=['POST'])
def api_upload_image():
    """Upload an image, return hashed filename (timestamp + original extension)"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Generate unique filename: time_hash + extension
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = hashlib.md5(f"{time.time()}{file.filename}".encode()).hexdigest()
    filename = f"{unique_name}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    
    # Return the path that can be stored in the quiz JSON
    return jsonify({'filename': filename, 'url': f'{UPLOAD_FOLDER}/{filename}'})

# Optional: serve uploaded images (if not already served by static folder)
@app.route('/static/quiz-figures/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)



def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    print("Servidor Flask-Quiz iniciado!")
    print(f"Aponte seu navegador de host (professor) para: http://localhost:5000/host")
    print(f"Aponte seu navegador de admin para: http://localhost:5000/admin") # ### MUDANÇA ### (Faltava)
    local_ip = get_local_ip()
    print(f"Alunos devem acessar: http://{local_ip}:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
