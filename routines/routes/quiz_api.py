"""API do editor: turmas, quizzes por turma, cópia entre turmas e import/export."""

import hashlib
import json
import logging
import os
import time
import zipfile
from io import BytesIO

from flask import jsonify, request, send_file, send_from_directory

from routines import classes, constants, files_handler, runtime
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)


# -------------------- Turmas --------------------
def api_list_classes():
    """Lista as turmas e informa qual delas está em jogo, se houver."""
    return jsonify({
        'classes': classes.brief_list(),
        'active': runtime.game_state.get('class_slug'),
    })


def api_create_class():
    """Cria uma turma."""
    data = request.get_json(silent=True) or {}
    slug, error = classes.create(data.get('name'))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'slug': slug, 'name': classes.name_of(slug)}), 201


def api_rename_class(class_slug):
    """Renomeia uma turma (a pasta dos quizzes não muda)."""
    data = request.get_json(silent=True) or {}
    error = classes.rename(class_slug, data.get('name'))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'slug': class_slug, 'name': classes.name_of(class_slug)})


def api_delete_class(class_slug):
    """Exclui uma turma e a pasta dos seus quizzes."""
    error = classes.delete(class_slug)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'message': 'Turma excluída.'})


# -------------------- Quizzes da turma --------------------
def api_list_quizzes(class_slug):
    """Nomes dos quizzes de uma turma."""
    if not classes.exists(class_slug):
        return jsonify({'error': 'Turma não encontrada'}), 404
    return jsonify(files_handler.get_quiz_list(class_slug))


def api_list_quizzes_by_class():
    """{slug: [nomes]} — usado pelo seletor de cópia entre turmas."""
    return jsonify(files_handler.list_quizzes_by_class())


def api_get_quiz(class_slug, quiz_name):
    """Retorna o JSON de um quiz."""
    try:
        quiz = files_handler.load_quiz(class_slug, quiz_name)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if quiz is None:
        return jsonify({'error': 'Quiz not found'}), 404
    return jsonify(quiz)


def api_save_quiz(class_slug, quiz_name):
    """Cria ou atualiza um quiz da turma."""
    data = request.get_json(silent=True)
    if not data or 'title' not in data or 'questions' not in data:
        return jsonify({'error': 'Invalid quiz data'}), 400

    try:
        files_handler.save_quiz(class_slug, quiz_name, data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'message': 'Quiz saved successfully'})


def api_delete_quiz(class_slug, quiz_name):
    """Exclui um quiz (arquivo principal, backup e temporário)."""
    try:
        removed = files_handler.delete_quiz(class_slug, quiz_name)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if not removed:
        return jsonify({'error': 'Quiz not found'}), 404
    return jsonify({'message': 'Quiz deleted'})


def api_copy_quiz(class_slug):
    """Copia um quiz de outra turma para esta."""
    data = request.get_json(silent=True) or {}
    from_class = data.get('from_class')
    from_quiz = data.get('quiz_name')
    if not from_class or not from_quiz:
        return jsonify({'error': 'Informe a turma e o quiz de origem.'}), 400

    new_name, error = files_handler.copy_quiz(
        from_class, from_quiz, class_slug, data.get('new_name')
    )
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'quiz_name': new_name, 'message': 'Quiz copiado.'})


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

    class_slug = request.form.get('class') or request.args.get('class')
    if not class_slug or not classes.exists(class_slug):
        return jsonify({'error': 'Turma de destino não informada ou inexistente.'}), 400

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

            # Define um nome único dentro da turma de destino
            base_name = quiz_data['title'].replace('/', '_').replace('\\', '_')
            quiz_name = files_handler.unique_quiz_name(class_slug, base_name)

            files_handler.save_quiz(class_slug, quiz_name, quiz_data)

            return jsonify({
                'success': True,
                'class': class_slug,
                'quiz_name': quiz_name,
                'quiz_data': quiz_data,
            })

    except zipfile.BadZipFile:
        return jsonify({'error': 'Arquivo .quiz corrompido (não é um ZIP válido)'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao processar o arquivo: {str(e)}'}), 500


def register(app):
    # Turmas
    app.add_url_rule('/api/classes', 'api_list_classes', api_list_classes, methods=['GET'])
    app.add_url_rule('/api/classes', 'api_create_class', api_create_class, methods=['POST'])
    app.add_url_rule('/api/classes/<class_slug>', 'api_rename_class', api_rename_class,
                     methods=['POST'])
    app.add_url_rule('/api/classes/<class_slug>', 'api_delete_class', api_delete_class,
                     methods=['DELETE'])

    # Quizzes de uma turma
    app.add_url_rule('/api/quizzes-by-class', 'api_list_quizzes_by_class',
                     api_list_quizzes_by_class, methods=['GET'])
    app.add_url_rule('/api/classes/<class_slug>/quizzes', 'api_list_quizzes',
                     api_list_quizzes, methods=['GET'])
    app.add_url_rule('/api/classes/<class_slug>/quiz/<quiz_name>', 'api_get_quiz',
                     api_get_quiz, methods=['GET'])
    app.add_url_rule('/api/classes/<class_slug>/quiz/<quiz_name>', 'api_save_quiz',
                     api_save_quiz, methods=['POST'])
    app.add_url_rule('/api/classes/<class_slug>/quiz/<quiz_name>', 'api_delete_quiz',
                     api_delete_quiz, methods=['DELETE'])
    app.add_url_rule('/api/classes/<class_slug>/copy', 'api_copy_quiz', api_copy_quiz,
                     methods=['POST'])

    # Figuras e pacotes .quiz
    app.add_url_rule('/api/upload_image', 'api_upload_image', api_upload_image, methods=['POST'])
    app.add_url_rule('/static/quiz-figures/<filename>', 'uploaded_file', uploaded_file)
    app.add_url_rule('/api/quiz/export', 'api_export_quiz', api_export_quiz, methods=['POST'])
    app.add_url_rule('/api/quiz/import', 'api_import_quiz', api_import_quiz, methods=['POST'])
