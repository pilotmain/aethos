import {create} from 'zustand';

import type {ChatMessage} from '../types';

type ChatState = {
  messages: ChatMessage[];
  pushMessage: (m: ChatMessage) => void;
  clear: () => void;
};

export const useChatStore = create<ChatState>(set => ({
  messages: [],
  pushMessage: m => set(s => ({messages: [...s.messages, m]})),
  clear: () => set({messages: []}),
}));
