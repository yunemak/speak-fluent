import { useEffect, useState } from 'react';
import { useConversation } from './hooks/useConversation.js';
import ConversationView from './components/ConversationView.jsx';
import HistorySidebar from './components/HistorySidebar.jsx';
import HistoryView from './components/HistoryView.jsx';
import { api } from './lib/api.js';
import styles from './App.module.css';

export default function App() {
  const conversation = useConversation();
  const [showText, setShowText] = useState(true);
  const [history, setHistory] = useState({ sessions: [], warnings: [], loading: true, error: '' });
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [entry, setEntry] = useState({ data: null, loading: false, error: '' });
  const [entryRefresh, setEntryRefresh] = useState(0);
  const historyAvailable = ['idle', 'complete'].includes(conversation.phase);
  const savedId = conversation.savedConversation?.id;

  useEffect(() => {
    const controller = new AbortController();
    setHistory(previous => ({ ...previous, loading: true, error: '' }));
    api.history(controller.signal).then(result => {
      if (!controller.signal.aborted) setHistory({ ...result, loading: false, error: '' });
    }).catch(error => {
      if (!controller.signal.aborted) setHistory(previous => ({ ...previous, loading: false, error: error.message }));
    });
    return () => controller.abort();
  }, [historyRefresh, savedId]);

  useEffect(() => {
    if (!selectedId || !historyAvailable) return;
    const controller = new AbortController();
    setEntry({ data: null, loading: true, error: '' });
    api.conversation(selectedId, controller.signal).then(data => {
      if (!controller.signal.aborted) setEntry({ data, loading: false, error: '' });
    }).catch(error => {
      if (!controller.signal.aborted) setEntry({ data: null, loading: false, error: error.message });
    });
    return () => controller.abort();
  }, [selectedId, entryRefresh, historyAvailable]);

  const start = () => {
    setSelectedId(null);
    void conversation.start();
  };

  const backToPractice = () => {
    void conversation.reset();
    setSelectedId(null);
    setEntry({ data: null, loading: false, error: '' });
  };

  const remove = async id => {
    await api.deleteConversation(id);
    setSelectedId(current => current === id ? null : current);
    setEntry(current => current.data?.id === id ? { data: null, loading: false, error: '' } : current);
    setHistory(current => ({ ...current, sessions: current.sessions.filter(session => session.id !== id) }));
    setHistoryRefresh(value => value + 1);
  };

  return <div className={styles.app}>
    <HistorySidebar {...history} disabled={!historyAvailable} selectedId={selectedId}
      onSelect={setSelectedId} onRefresh={() => setHistoryRefresh(value => value + 1)} onDelete={remove} />
    <main className={styles.main}>
      <header className={styles.header}>
        <div><strong>Speak Fluent</strong><span>A little practice, every day.</span></div>
        {!selectedId && <button className="quiet" onClick={() => setShowText(value => !value)} aria-pressed={!showText}>
          {showText ? 'Hide text' : 'Show text'}
        </button>}
      </header>
      {selectedId && historyAvailable
        ? <HistoryView key={selectedId} entry={entry.data?.id === selectedId ? entry.data : null} loading={entry.loading} error={entry.error}
          onStart={start} onBack={backToPractice} onRetry={() => setEntryRefresh(value => value + 1)}
          onDelete={() => remove(selectedId)} />
        : <ConversationView conversation={{ ...conversation, start }} showText={showText} />}
    </main>
  </div>;
}
