"""API do editor de quizzes: listar, salvar, excluir, importar e exportar."""

import hashlib
import json
import logging
import os
import time
import zipfile
from io import BytesIO

from flask import jsonify, request, send_file, send_from_directory

from routines import constants, files_handler
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)


def api_list_quizzes():
    """Lista os nomes dos quizzes disponíveis."""
    return jsonify(files_handler.get_quiz_list())


def api_get_quiz(quiz_name):
    """Retorna o JSON de um quiz."""
    quiz = files_handler.load_quiz(quiz_name)
    if quiz is None:
        return jsonify({'error': 'Quiz not found'}), 404
    return jsonify(quiz)


def api_save_quiz(quiz_name):
    """Cria ou atualiza um quiz."""
    data = request.get_json()
    if not data or 'title' not in data or 'questions' not in data:
        return jsonify({'error': 'Invalid quiz data'}), 400

    files_handler.save_quiz(quiz_name, data)
    return jsonify({'message': 'Quiz saved successfully'})


def api_delete_quiz(quiz_name):
    """Exclui um quiz (arquivo principal, backup e temporário)."""
    path = os.path.join(constants.QUIZZES_FOLDER, f'{quiz_name}.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Quiz not found'}), 404

    for suffix in ('', '.bak', '.tmp'):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass
    return jsonify({'message': 'Quiz deleted'})


def api_upload_image():
    """Envia uma figura e devolve o nome único gerado."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not files_handler.allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = hashlib.md5(f"{time.time()}{file.filename}".encode()).hexdigest()
    filename = f"{unique_name}.{ext}"
    file.save(os.path.join(constants.UPLOAD_FOLDER, filename))

    return jsonify({
        'filename': filename,
        'url': f'{constants.UPLOAD_FOLDER}/{filename}',
    })


def uploaded_file(filename):
    """Serve as figuras enviadas pelo editor."""
    return send_from_directory(constants.UPLOAD_FOLDER, filename)


def api_export_quiz():
    """Empacota JSON + imagens em um arquivo `.quiz` para download."""
    data = request.get_json()
    if not data or 'title' not in data or 'questions' not in data:
        return jsonify({'error': 'Dados do quiz inválidos'}), 400

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Adiciona o quiz.json
        quiz_json_str = json.dumps(data, indent=2, ensure_ascii=False)
        zip_file.writestr('quiz.json', quiz_json_str)

        # 2. Adiciona as figuras (se existirem)
        for idx, q in enumerate(data['questions']):
            fig = q.get('figure')
            if fig and fig != 'none':
                fig_path = os.path.join(constants.UPLOAD_FOLDER, fig)
                if os.path.exists(fig_path):
                    zip_file.write(fig_path, arcname=f'figures/{fig}')
                else:
                    log.warning(f'Aviso: figura "{fig}" não encontrada para a pergunta {idx}')

    zip_buffer.seek(0)
    safe_title = data['title'].replace('/', '_').replace('\\', '_')
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f'{safe_title}.quiz',
        mimetype='application/zip',
    )


def api_import_quiz():
    """Recebe um `.quiz`, extrai JSON e imagens e salva no servidor."""
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Arquivo vazio'}), 400
    if not file.filename.endswith('.quiz'):
        return jsonify({'error': 'O arquivo deve ter extensão .quiz'}), 400

    try:
        zip_data = file.read()
        with zipfile.ZipFile(BytesIO(zip_data), 'r') as zip_file:
            if 'quiz.json' not in zip_file.namelist():
                return jsonify({'error': 'Arquivo .quiz inválido: não contém quiz.json'}), 400

            quiz_json_str = zip_file.read('quiz.json').decode('utf-8')
            quiz_data = json.loads(quiz_json_str)

            if 'title' not in quiz_data or 'questions' not in quiz_data:
                return jsonify({'error': 'quiz.json mal formatado (faltando title ou questions)'}), 400

            # Mapeia todas as figuras dentro da pasta 'figures/'
            figure_files = {}
            for name in zip_file.namelist():
                if name.startswith('figures/') and not name.endswith('/'):
                    orig_filename = os.path.basename(name)
                    figure_files[orig_filename] = zip_file.read(name)

            # Atualiza referências das figuras e salva as imagens com nomes únicos
            for q in quiz_data['questions']:
                fig = q.get('figure')
                if fig and fig != 'none' and fig in figure_files:
                    ext = fig.rsplit('.', 1)[1].lower() if '.' in fig else 'png'
                    novo_nome = hashlib.md5(f"{time.time()}{fig}".encode()).hexdigest()
                    novo_nome = f"{novo_nome}.{ext}"
                    caminho_imagem = os.path.join(constants.UPLOAD_FOLDER, novo_nome)
                    with open(caminho_imagem, 'wb') as img_f:
                        img_f.write(figure_files[fig])
                    q['figure'] = novo_nome
                elif fig and fig != 'none':
                    # Figura referenciada mas não presente no pacote
                    q['figure'] = 'none'

            # Define um nome único para o arquivo do quiz (evita sobrescrita)
            base_name = quiz_data['title'].replace('/', '_').replace('\\', '_')
            quiz_name = base_name
            contador = 1
            while os.path.exists(os.path.join(constants.QUIZZES_FOLDER, f'{quiz_name}.json')):
                quiz_name = f"{base_name}_{contador}"
                contador += 1

            files_handler.save_quiz(quiz_name, quiz_data)

            return jsonify({
                'success': True,
                'quiz_name': quiz_name,
                'quiz_data': quiz_data,
            })

    except zipfile.BadZipFile:
        return jsonify({'error': 'Arquivo .quiz corrompido (não é um ZIP válido)'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar o arquivo: {str(e)}'}), 500


def register(app):
    app.add_url_rule('/api/quizzes', 'api_list_quizzes', api_list_quizzes, methods=['GET'])
    app.add_url_rule('/api/quiz/<quiz_name>', 'api_get_quiz', api_get_quiz, methods=['GET'])
    app.add_url_rule('/api/quiz/<quiz_name>', 'api_save_quiz', api_save_quiz, methods=['POST'])
    app.add_url_rule('/api/quiz/<quiz_name>', 'api_delete_quiz', api_delete_quiz, methods=['DELETE'])
    app.add_url_rule('/api/upload_image', 'api_upload_image', api_upload_image, methods=['POST'])
    app.add_url_rule('/static/quiz-figures/<filename>', 'uploaded_file', uploaded_file)
    app.add_url_rule('/api/quiz/export', 'api_export_quiz', api_export_quiz, methods=['POST'])
    app.add_url_rule('/api/quiz/import', 'api_import_quiz', api_import_quiz, methods=['POST'])
