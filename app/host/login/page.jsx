"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function HostLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const submitLogin = async (event) => {
    event.preventDefault();
    setError('');

    const response = await fetch('/api/host/login', {
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

    router.push('/host');
  };

  return (
    <section className="card page-grid" style={{ maxWidth: 560, margin: '0 auto' }}>
      <div>
        <span className="pill">Host</span>
        <h1 className="hero-title">Login do apresentador</h1>
        <p className="hero-copy">Use a mesma senha do admin para abrir a sala do professor.</p>
      </div>

      <form className="stack" onSubmit={submitLogin}>
        <input type="password" placeholder="Senha do host" value={password} onChange={(event) => setPassword(event.target.value)} />
        {error ? <div className="result-banner" style={{ borderColor: 'rgba(239, 68, 68, 0.35)' }}>{error}</div> : null}
        <button type="submit">Entrar</button>
      </form>
    </section>
  );
}