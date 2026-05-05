"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AdminLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const submitLogin = async (event) => {
    event.preventDefault();
    setError('');

    const response = await fetch('/api/admin/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ password })
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setError(payload.error || 'Falha no login');
      return;
    }

    router.push('/admin');
  };

  return (
    <section className="card page-grid" style={{ maxWidth: 560, margin: '0 auto' }}>
      <div>
        <span className="pill">Admin</span>
        <h1 className="hero-title">Login administrativo</h1>
        <p className="hero-copy">Acesse o painel para gerenciar os usuários autorizados.</p>
      </div>

      <form className="stack" onSubmit={submitLogin}>
        <input type="password" placeholder="Senha do admin" value={password} onChange={(event) => setPassword(event.target.value)} />
        {error ? <div className="result-banner" style={{ borderColor: 'rgba(239, 68, 68, 0.35)' }}>{error}</div> : null}
        <button type="submit">Entrar</button>
      </form>
    </section>
  );
}