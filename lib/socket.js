import { io } from 'socket.io-client';

let socket;

export function getSocket() {
  if (typeof window === 'undefined') {
    return null;
  }

  if (!socket) {
    socket = io();
  }

  return socket;
}