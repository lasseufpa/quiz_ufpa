import { act } from 'react-dom/test-utils';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PlayerPage from '@/app/page';
import { getSocket } from '@/lib/socket';

jest.mock('@/lib/socket', () => ({
  getSocket: jest.fn()
}));

function createMockSocket() {
  const handlers = {};
  return {
    id: 'socket-1',
    emit: jest.fn(),
    on: (event, handler) => {
      handlers[event] = handler;
    },
    off: (event) => {
      delete handlers[event];
    },
    trigger: (event, payload) => {
      if (handlers[event]) {
        handlers[event](payload);
      }
    }
  };
}

describe('PlayerPage', () => {
  beforeEach(() => {
    localStorage.clear();
    window.alert = jest.fn();
  });

  it('requires a nickname before joining', async () => {
    const socket = createMockSocket();
    getSocket.mockReturnValue(socket);

    render(<PlayerPage />);

    await waitFor(() => expect(getSocket).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /entrar/i }));
    expect(window.alert).toHaveBeenCalledWith('Adicione um nome.');
    expect(socket.emit).not.toHaveBeenCalledWith('player_join', expect.anything());
  });

  it('moves to waiting view after join success', async () => {
    const socket = createMockSocket();
    getSocket.mockReturnValue(socket);

    render(<PlayerPage />);

    await waitFor(() => expect(getSocket).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText('Seu nome'), { target: { value: 'Alice' } });
    fireEvent.click(screen.getByRole('button', { name: /entrar/i }));

    expect(socket.emit).toHaveBeenCalledWith('player_join', { nickname: 'Alice' });

    act(() => {
      socket.trigger('join_success', { nickname: 'Alice', session_token: 'token-1' });
    });

    expect(screen.getByText('Sala de espera')).toBeInTheDocument();
  });
});
