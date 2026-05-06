const nicknameInput = document.getElementById('nickname-input');
const addBtn = document.getElementById('add-btn');
const userListEl = document.getElementById('user-list');

// 1. Avisa o servidor que somos um admin e pede a lista
socket.emit('admin_join');

// 2. Recebe a lista de usuários do servidor
socket.on('update_user_list', (users) => {
    userListEl.innerHTML = ''; // Limpa a lista antiga
    if (users.length === 0) {
        userListEl.innerHTML = '<li class="user-list-item">Nenhum usuário cadastrado.</li>';
    }

    users.forEach(nickname => {
        const li = document.createElement('li');
        li.classList.add('user-list-item');

        // --- Cria a estrutura HTML interna do <li> ---

        // (A) O nome (visível por padrão)
        const spanName = document.createElement('span');
        spanName.classList.add('nickname-display');
        spanName.textContent = nickname;

        // (B) O formulário de edição (escondido por padrão)
        const editForm = document.createElement('div');
        editForm.classList.add('edit-form');
        editForm.style.display = 'none';

        const editInput = document.createElement('input');
        editInput.type = 'text';
        editInput.value = nickname;

        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Salvar';
        saveBtn.classList.add('btn-save');

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancelar';
        cancelBtn.classList.add('btn-cancel');

        editForm.appendChild(editInput);

        // (C) Os botões de ação (visíveis por padrão)
        const actionsDiv = document.createElement('div');
        actionsDiv.classList.add('actions');

        const editBtn = document.createElement('button');
        editBtn.textContent = 'Editar';
        editBtn.classList.add('btn-edit');

        const removeBtn = document.createElement('button');
        removeBtn.textContent = 'Remover';
        removeBtn.classList.add('btn-remove');

        actionsDiv.appendChild(editBtn);
        actionsDiv.appendChild(removeBtn);
        actionsDiv.appendChild(saveBtn); // Salvar e Cancelar ficam aqui
        actionsDiv.appendChild(cancelBtn); // para facilitar o alinhamento
        saveBtn.style.display = 'none';
        cancelBtn.style.display = 'none';

        // Monta o <li>
        li.appendChild(spanName);
        li.appendChild(editForm);
        li.appendChild(actionsDiv);

        userListEl.appendChild(li);

        // --- Adiciona os Event Listeners ---

        // CLIQUE EM "EDITAR"
        editBtn.addEventListener('click', () => {
            // Esconde o nome e os botões "Editar/Remover"
            spanName.style.display = 'none';
            editBtn.style.display = 'none';
            removeBtn.style.display = 'none';

            // Mostra o formulário de edição e os botões "Salvar/Cancelar"
            editForm.style.display = 'block';
            saveBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'inline-block';
            editInput.focus();
            editInput.select();
        });

        // CLIQUE EM "CANCELAR"
        cancelBtn.addEventListener('click', () => {
            // Mostra o nome e os botões "Editar/Remover"
            spanName.style.display = 'block';
            editBtn.style.display = 'inline-block';
            removeBtn.style.display = 'inline-block';

            // Esconde o formulário de edição e os botões "Salvar/Cancelar"
            editForm.style.display = 'none';
            saveBtn.style.display = 'none';
            cancelBtn.style.display = 'none';

            // Reseta o valor do input (caso o usuário tenha digitado algo)
            editInput.value = nickname;
        });

        // CLIQUE EM "REMOVER"
        removeBtn.addEventListener('click', () => {
            if (confirm(`Tem certeza que deseja remover o usuário "${nickname}"?`)) {
                socket.emit('remove_user', { 'nickname': nickname });
            }
        });

        // CLIQUE EM "SALVAR"
        // ### AQUI ESTAVA O BUG: ()E> foi corrigido para () => ###
        saveBtn.addEventListener('click', () => {
            const newNickname = editInput.value.trim();
            if (newNickname && newNickname !== nickname) {
                socket.emit('edit_user', {
                    'old_nickname': nickname,
                    'new_nickname': newNickname
                });
            } else if (newNickname === nickname) {
                // Se não mudou, apenas cancela a edição
                cancelBtn.click();
            } else {
                alert('O nome não pode ficar em branco.');
            }
        });

        // Permite salvar com "Enter"
        editInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                saveBtn.click();
            }
        });
    });
});

// 4. Envia um novo usuário para ADICIONAR (Sem mudanças)
addBtn.addEventListener('click', () => {
    const nickname = nicknameInput.value.trim();
    if (nickname) {
        socket.emit('add_user', { 'nickname': nickname });
        nicknameInput.value = ''; // Limpa o campo
    }
});
nicknameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        addBtn.click();
    }
});

// Recebe erros do servidor
socket.on('admin_error', (data) => {
    alert('Erro: ' + data.message);
});
