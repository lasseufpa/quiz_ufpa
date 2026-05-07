import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminLoginPage from '@/app/admin/login/page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn()
  })
}));

describe('AdminLoginPage', () => {
  afterEach(() => {
    if (global.fetch && global.fetch.mockRestore) {
      global.fetch.mockRestore();
    }
  });

  it('shows an error when login fails', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: 'Falha no login' })
    });

    render(<AdminLoginPage />);

    fireEvent.change(screen.getByPlaceholderText('Senha do admin'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /entrar/i }));

    await waitFor(() => expect(screen.getByText('Falha no login')).toBeInTheDocument());
  });
});
