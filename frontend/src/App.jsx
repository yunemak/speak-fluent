import { useState } from 'react';
import { useConversation } from './hooks/useConversation.js';
import ConversationView from './components/ConversationView.jsx';
import styles from './App.module.css';

export default function App() {
  const conversation = useConversation();
  const [showText, setShowText] = useState(true);
  return <div className={styles.app}>
    <aside className={styles.sidebar}>
      <a className={styles.brand} href="/" aria-label="Speak Fluent home">sf<span>●</span></a>
      <h2>Conversations</h2>
      <p className={styles.empty}>Your practice has a place here.</p>
      <p className={styles.note}>Saved history arrives in the next build step.</p>
      <div className={styles.local}><span /> Runs on your computer</div>
    </aside>
    <main className={styles.main}>
      <header className={styles.header}>
        <div><strong>Speak Fluent</strong><span>A little practice, every day.</span></div>
        <button className="quiet" onClick={() => setShowText(value => !value)} aria-pressed={!showText}>
          {showText ? 'Hide text' : 'Show text'}
        </button>
      </header>
      <ConversationView conversation={conversation} showText={showText} />
      <footer className={styles.footer}>Just a conversation. No scores. No pressure.</footer>
    </main>
  </div>;
}
