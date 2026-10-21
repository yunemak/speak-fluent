async function request(path, { signal, ...options } = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, { ...options, signal });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Cannot reach the local Python service. Start the backend, then retry.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `Local service failed (${response.status}). Please retry.`);
  }
  return response;
}

const json = async (path, body, signal) => (await request(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body), signal,
})).json();

export const api = {
  save: (body, signal) => json('/conversations', body, signal),
  history: async signal => (await request('/conversations', { signal })).json(),
  conversation: async (id, signal) => (await request(`/conversations/${encodeURIComponent(id)}`, { signal })).json(),
  deleteConversation: async (id, signal) => (await request(`/conversations/${encodeURIComponent(id)}`, {
    method: 'DELETE', signal,
  })).json(),
  health: async signal => (await request('/health', { signal })).json(),
  reply: (body, signal) => json('/reply', body, signal),
  report: (body, signal) => json('/report', body, signal),
  speech: async (body, signal) => (await request('/speech', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  })).arrayBuffer(),
  transcribe: async (wav, signal) => (await request('/transcribe', {
    method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: wav, signal,
  })).json(),
};
