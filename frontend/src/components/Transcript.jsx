import styles from './Transcript.module.css';

export default function Transcript({
  turns = [], report = '', showText = true, headerRight = 'Live transcript', endRef, children,
}) {
  // With AI text hidden, keep only the learner's most recent turn so earlier
  // practice remains private and the screen stays focused on what they just said.
  const latestUserTurn = showText ? null : turns.findLast(turn => turn.role === 'user');
  const visibleTurns = showText ? turns : latestUserTurn ? [latestUserTurn] : [];
  return <div className={styles.transcript}>
    <div className={styles.header}>
      <span>THIS CONVERSATION</span>
      <span>{showText ? headerRight : 'Your latest message'}</span>
    </div>
    {visibleTurns.map(turn => (
      <article key={turn.id} className={turn.role === 'user' ? styles.user : styles.assistant}>
        <span className={styles.role}>{turn.role === 'user' ? 'You' : 'Your partner'}</span>
        <p>{turn.text}</p>
        {turn.interrupted && <small>Interrupted — generated reply shown; not all words were spoken.</small>}
      </article>
    ))}
    {report && showText && <article className={styles.report}>
      <h2>Your feedback</h2><p>{report}</p>
    </article>}
    {children}
    <div ref={endRef} className={styles.end} aria-hidden="true" />
  </div>;
}
