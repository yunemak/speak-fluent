import { useEffect, useRef } from 'react';
import Robot from './Robot.jsx';
import styles from './ConversationView.module.css';

const labels = {
  idle: 'Your space to speak', starting: 'Getting ready', listening: 'Listening',
  transcribing: 'Understanding your words', thinking: 'Thinking', speaking: 'Speaking',
  'preparing-feedback': 'Preparing feedback', 'feedback-speaking': 'Your feedback',
  saving: 'Saving your conversation', complete: 'A little more fluent', error: 'Let’s get you back to practice',
};

export default function ConversationView({ conversation: c, showText }) {
  const ready = ['idle', 'complete'].includes(c.phase);
  const endRef = useRef(null);
  const followingRef = useRef(true);
  const lastTurn = c.turns[c.turns.length - 1];

  // Keep the newest message in view unless the learner has deliberately
  // scrolled up to reread earlier turns.
  useEffect(() => {
    const update = () => {
      const page = document.scrollingElement || document.documentElement;
      followingRef.current = page.scrollHeight - page.scrollTop - window.innerHeight < 160;
    };
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);

  useEffect(() => {
    if (!followingRef.current || !endRef.current) return;
    const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const frame = requestAnimationFrame(() => {
      endRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' });
    });
    return () => cancelAnimationFrame(frame);
  }, [c.turns.length, lastTurn?.text, lastTurn?.interrupted, c.report, c.savedConversation, showText]);

  return <section className={styles.view}>
    <p className={styles.eyebrow}>EVERYDAY ENGLISH · YOUR OWN PACE</p>
    <Robot speaking={c.speaking} />
    <h1>{labels[c.phase]}</h1>
    <p className={styles.description} role="status">
      {c.phase === 'idle' ? 'Find your words. We’ll keep the conversation going.' :
        c.phase === 'complete' ? 'Saved on your computer. Ready for another conversation?' :
          c.phase === 'saving' ? 'Keeping your transcript and feedback together…' :
          c.userSpeaking ? 'Take your time. I’m listening.' :
            c.phase === 'listening' ? 'Your turn. Say goodbye whenever you’re ready for feedback.' :
              c.phase === 'starting' ? 'Checking local models and opening your microphone…' :
                c.phase === 'preparing-feedback' ? 'Looking back at your words for useful suggestions…' :
                  c.phase === 'feedback-speaking' ? 'Practice is finished. Listen to your feedback, then start again whenever you like.' :
                    c.phase === 'error' ? 'Your conversation stays here while you retry.' :
                    'You can speak naturally. No need to press a button for each turn.'}
    </p>
    {c.phase === 'idle' && <p className={styles.motto}>Just a conversation. No scores. No pressure.</p>}
    {ready && <button className={styles.start} onClick={c.start}>
      <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" />
      </svg>
      {c.phase === 'complete' ? 'Start another conversation' : 'Start a conversation'}
    </button>}
    {c.phase === 'idle' && <p className={styles.hint}>Put on your headphones. Your partner speaks first.</p>}
    {c.warning && <div className={styles.warning} role="alert">
      <p>{c.warning}</p>
      {c.retryable && <button className="quiet" onClick={c.retry}>{c.retryLabel}</button>}
    </div>}
    {c.turns.length > 0 && <div className={styles.transcript}>
      <div className={styles.transcriptHeader}><span>THIS CONVERSATION</span><span>{showText ? 'Live transcript' : 'AI text hidden'}</span></div>
      {c.turns.filter(turn => showText || turn.role === 'user').map(turn => <article key={turn.id} className={turn.role === 'user' ? styles.user : styles.assistant}>
        <span className={styles.role}>{turn.role === 'user' ? 'You' : 'Your partner'}</span>
        <p>{turn.text}</p>
        {turn.interrupted && <small>Interrupted — generated reply shown; not all words were spoken.</small>}
      </article>)}
      {c.report && showText && <article className={styles.report}>
        <h2>Your feedback</h2><p>{c.report}</p>
      </article>}
      {c.savedConversation && <p className={styles.hint}>Saved in <code>data/conversations/{c.savedConversation.filename}</code>. Open it from the sidebar anytime.</p>}
      <div ref={endRef} className={styles.end} aria-hidden="true" />
    </div>}
  </section>;
}
