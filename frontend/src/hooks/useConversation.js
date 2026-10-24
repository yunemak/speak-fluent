import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { BrowserAudio } from '../lib/audio.js';
import { Conversation, initialState } from '../lib/conversation.js';

export function useConversation() {
  const [state, setState] = useState(initialState);
  const controller = useRef(null);
  if (!controller.current) controller.current = new Conversation(api, new BrowserAudio(), setState);
  useEffect(() => {
    const conversation = controller.current;
    return () => { void conversation.dispose(); };
  }, []);
  return { ...state, start: () => controller.current.start(), retry: () => controller.current.retry(),
    reset: () => controller.current.reset() };
}
