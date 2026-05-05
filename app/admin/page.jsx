"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getSocket } from '@/lib/socket';

export default function AdminPage() {
  const router = useRouter();
  const [socket, setSocket] = useState(null);
  const [users, setUsers] = useState([]);
  const [nickname, setNickname] = useState('');
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    setSocket(getSocket());
  }, []);

  useEffect(() => {
    if (!socket) {
      return;
    }

    const verifySession = async () => {
      const response = await fetch('/api/admin/session');
      const payload = await response.json();
      if (!payload.loggedIn) {
        router.push('/admin/login');
      }
    };

    verifySession();
    socket.emit('admin_join');

    const onUsers = (list) => setUsers(list || []);
    const onAdminError = (data) => alert(data.message || 'Erro');

    socket.on('update_user_list', onUsers);
    socket.on('admin_error', onAdminError);

    return () => {
      socket.off('update_user_list', onUsers);
      socket.off('admin_error', onAdminError);
    };
  }, [router, socket]);

  const addUser = () => {
    const trimmed = nickname.trim();
    if (!trimmed || !socket) {
      return;
    }

    socket.emit('add_user', { nickname: trimmed });
    setNickname('');
  };

  const removeUser = (user) => {
    if (window.confirm(`Tem certeza que deseja remover "${user}"?`)) {
      socket?.emit('remove_user', { nickname: user });
    }
  };

  const saveUser = (user) => {
    const trimmed = draft.trim();
    if (!trimmed) {
      return;
    }

    socket?.emit('edit_user', { old_nickname: user, new_nickname: trimmed });
    setEditing(null);
    setDraft('');
  };

  return (
    <section className="page-grid">
      <div className="card page-grid">
        <div className="toolbar" style={{ justifyContent: 'space-between' }}>
          <div>
            <span className="pill">Admin</span>
            <h1 className="hero-title">Gerenciar usuários</h1>
            <p className="hero-copy">Somente usuários cadastrados podem entrar no quiz.</p>
          </div>
          <button className="ghost" onClick={async () => {
            await fetch('/api/admin/logout', { method: 'POST' });
            router.push('/admin/login');
          }}>Sair</button>
        </div>

        <div className="toolbar">
          <input value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="Nome do novo jogador" />
          <button onClick={addUser}>Adicionar</button>
        </div>
      </div>

      <div className="card page-grid">
        <h2 className="section-title">Usuários cadastrados</h2>
        <div className="list">
          {users.length === 0 ? (
            <div className="result-banner">Nenhum usuário cadastrado.</div>
          ) : users.map((user) => (
            <div key={user} className="admin-list-item">
              {editing === user ? (
                <div className="toolbar">
                  <input value={draft} onChange={(event) => setDraft(event.target.value)} style={{ flex: 1 }} />
                  <button className="success" onClick={() => saveUser(user)}>Salvar</button>
                  <button className="ghost" onClick={() => { setEditing(null); setDraft(''); }}>Cancelar</button>
                </div>
              ) : (
                <div className="toolbar" style={{ justifyContent: 'space-between' }}>
                  <strong>{user}</strong>
                  <div className="toolbar">
                    <button className="warning" onClick={() => { setEditing(user); setDraft(user); }}>Editar</button>
                    <button className="danger" onClick={() => removeUser(user)}>Remover</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}