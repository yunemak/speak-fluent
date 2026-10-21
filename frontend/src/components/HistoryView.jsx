import styles from './HistoryView.module.css';

export default function HistoryView({ entry, loading, error, onRetry, onStart, onBack }) {
  return <section className={styles.view} aria-label="Saved conversation">
    <div className={styles.actions}>
      <button className="quiet" onClick={onBack}>Back to practice</button>
      <button className={styles.start} onClick={onStart}>Start a conversation</button>
    </div>
    {loading && <p role="status">Opening your conversation…</p>}
    {error && <div className={styles.warning} role="alert"><p>{error}</p><button className="quiet" onClick={onRetry}>Retry opening</button></div>}
    {entry && <>
      <h1>{entry.title}</h1>
      <p className={styles.note}>Your transcript and feedback, saved locally as Markdown.</p>
      <pre className={styles.document}>{entry.markdown}</pre>
    </>}
  </section>;
}
