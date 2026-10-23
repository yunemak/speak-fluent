export const initialState = () => ({
  phase: 'idle', turns: [], report: '', speaking: false,
  userSpeaking: false, warning: '', retryable: false, retryLabel: 'Retry', sessionId: null,
  savedConversation: null,
});

// Reports are spoken paragraph by paragraph. A small chunk keeps the wait for
// first audio short; the next chunk is synthesised while the current one plays.
export function speechChunks(text, limit = 900) {
  const chunks = [];
  while (text.length > limit) {
    let end = text.lastIndexOf('\n\n', limit);
    if (end < limit / 2) end = text.lastIndexOf(' ', limit);
    if (end < limit / 2) end = limit;
    // Do not split a UTF-16 surrogate pair in an unusual long unbroken string.
    if (/[\uD800-\uDBFF]/.test(text[end - 1])) end -= 1;
    chunks.push(text.slice(0, end));
    text = text.slice(end);
  }
  if (text) chunks.push(text);
  return chunks;
}

// Framework-independent so the actual interruption/queue logic can be race-tested.
export class Conversation {
  constructor(api, audio, publish) {
    this.api = api;
    this.audio = audio;
    this.publish = publish;
    this.state = initialState();
    this.generation = 0;
    this.session = 0;
    this.queue = [];
    this.accepting = false;
    this.draining = false;
    this.needsReply = false;
  }

  update(changes) {
    this.state = { ...this.state, ...changes };
    this.publish(this.state);
  }

  invalidate() {
    this.generation += 1;
    this.pending?.abort();
    this.pending = null;
    this.audio.stop();
    if (this.playingTurn) {
      this.update({ turns: this.state.turns.map(turn => turn.id === this.playingTurn ? { ...turn, interrupted: true } : turn) });
      this.playingTurn = null;
    }
    this.update({ speaking: false });
  }

  async start() {
    // unlock() runs before the first await, inside the click's user activation.
    const unlocked = this.audio.unlock();
    const session = ++this.session;
    this.lifetime?.abort();
    this.lifetime = new AbortController();
    this.invalidate();
    this.queue = [];
    this.draining = false;
    this.needsReply = false;
    this.accepting = false;
    this.retryAction = null;
    this.state = { ...initialState(), phase: 'starting', sessionId: crypto.randomUUID(), createdAt: new Date().toISOString() };
    this.update({});
    try {
      await unlocked;
      const health = await this.api.health(this.lifetime.signal);
      if (session !== this.session) return;
      if (!health.ready) throw new Error(health.problems.join('\n'));
      await this.listen();
      if (session !== this.session) return;
      this.accepting = true;
      await this.respond(true);
    } catch (error) {
      if (session !== this.session) return;
      await this.audio.close();
      this.fail(error, () => this.start());
    }
  }

  fail(error, retry, retryLabel = 'Retry') {
    if (error.name === 'AbortError') return;
    if (this.playingTurn) {
      this.update({ turns: this.state.turns.map(turn => turn.id === this.playingTurn ? { ...turn, interrupted: true } : turn) });
      this.playingTurn = null;
    }
    this.retryAction = retry;
    this.update({ phase: 'error', speaking: false, warning: error.message, retryable: true, retryLabel });
  }

  async listen() {
    const session = this.session;
    await this.audio.listen({
      onSpeechStart: () => { if (session === this.session) this.speechStart(); },
      onSpeechEnd: (wav, options) => { if (session === this.session) this.speechEnd(wav, options); },
      onError: error => {
        if (session !== this.session || !this.accepting) return;
        this.invalidate();
        this.update({ userSpeaking: false });
        this.fail(error, async () => {
          await this.listen();
          if (session !== this.session) return;
          this.update({ phase: 'listening' });
          await this.drain();
        }, 'Retry microphone');
      },
    });
  }

  speechStart() {
    if (!this.accepting || this.state.phase === 'error') return;
    this.invalidate();
    this.update({ userSpeaking: true, phase: 'listening', warning: '' });
  }

  speechEnd(wav, { farewellOnly = false } = {}) {
    if (!this.accepting || this.state.phase === 'error') return;
    if (!farewellOnly) this.update({ userSpeaking: false });
    this.queue.push({ wav, farewellOnly });
    void this.drain();
  }

  async drain() {
    if (this.draining || !this.accepting) return;
    const session = this.session;
    this.draining = true;
    try {
      while (this.queue.length && this.accepting) {
        const { wav, farewellOnly } = this.queue[0];
        if (!farewellOnly) this.update({ phase: 'transcribing' });
        // Retain the head until success so Retry never loses an utterance.
        let result;
        try {
          result = await this.api.transcribe(wav, this.lifetime.signal);
        } catch (error) {
          if (session !== this.session) return;
          if (!farewellOnly) throw error;
          // A background check of unconfirmed noise must not break a live reply.
          this.queue.shift();
          continue;
        }
        if (session !== this.session) return;
        this.queue.shift();
        // Short noises never stop playback, change UI state, or become turns.
        // Only a recognized whole closing phrase may finish the session.
        if (farewellOnly && !result.is_farewell) continue;
        if (!result.text.trim()) {
          this.update({ warning: "I didn’t catch that—please try again." });
          continue;
        }
        this.update({ turns: [...this.state.turns, {
          id: crypto.randomUUID(), role: 'user', text: result.text, interrupted: false,
        }], warning: '' });
        this.needsReply = true;
        if (result.is_farewell) {
          this.accepting = false;
          this.queue = [];
          this.needsReply = false;
          this.invalidate();
          this.update({ userSpeaking: false });
          await this.audio.pauseInput();
          await this.respond(false, true);
          return;
        }
      }
    } catch (error) {
      if (session === this.session) this.fail(error, () => this.drain());
      return;
    } finally {
      if (session === this.session) this.draining = false;
    }
    if (session !== this.session || !this.accepting || this.state.userSpeaking) return;
    if (this.needsReply) {
      this.needsReply = false;
      void this.respond(false);
    } else if (this.state.phase === 'transcribing') {
      this.update({ phase: 'listening' });
    }
  }

  async respond(opening, report = false, cached = null) {
    this.invalidate();
    const generation = this.generation;
    const session = this.session;
    const controller = new AbortController();
    this.pending = controller;
    const current = () => session === this.session && generation === this.generation && !controller.signal.aborted;
    const request_id = `${this.state.sessionId}:${generation}`;
    const delivery = cached || { text: null, chunks: null, index: 0, audio: null };
    this.update({ phase: report ? 'preparing-feedback' : 'thinking', warning: '', retryable: false });
    try {
      if (!delivery.text) {
        const result = await this.api[report ? 'report' : 'reply']({ request_id, opening, turns: this.state.turns }, controller.signal);
        if (!current()) return;
        if (result.request_id !== request_id) throw new Error('Received an outdated response. Please retry.');
        delivery.text = report ? result.report_text : result.text;
        if (report) this.update({ report: delivery.text });
      }
      delivery.chunks ??= report ? speechChunks(delivery.text) : [delivery.text];
      while (delivery.index < delivery.chunks.length) {
        if (!delivery.audio) {
          const ahead = delivery.next;
          delivery.next = null;
          delivery.audio = ahead ? await ahead : null;
          if (!delivery.audio) {
            delivery.audio = await this.api.speech({ request_id, text: delivery.chunks[delivery.index] }, controller.signal);
          }
        }
        if (!current()) return;
        const following = delivery.chunks[delivery.index + 1];
        if (following && !delivery.next) {
          // Synthesise the next chunk during playback so speech stays continuous.
          delivery.next = this.api.speech({ request_id, text: following }, controller.signal)
            .catch(() => null);
        }
        const result = await this.audio.play(delivery.audio, current, () => {
          if (!current()) return;
          if (!report) {
            this.playingTurn = crypto.randomUUID();
            this.update({ turns: [...this.state.turns, {
              id: this.playingTurn, role: 'assistant', text: delivery.text, interrupted: false,
            }] });
          }
          this.update({ phase: report ? 'feedback-speaking' : 'speaking', speaking: true });
        });
        if (!current()) return;
        this.playingTurn = null;
        this.update({ speaking: false });
        if (result !== 'ended') return;
        delivery.index += 1;
        delivery.audio = null;
        if (report && delivery.index < delivery.chunks.length && !delivery.next) {
          this.update({ phase: 'preparing-feedback' });
        }
      }
      if (report) {
        await this.audio.close();
        if (current()) {
          this.update({ completedAt: new Date().toISOString() });
          await this.save();
        }
      } else {
        this.update({ phase: 'listening' });
      }
    } catch (error) {
      if (current()) this.fail(error, () => this.respond(opening, report, delivery));
    }
  }

  async save() {
    const session = this.session;
    this.update({ phase: 'saving', warning: '', retryable: false });
    try {
      const saved = await this.api.save({
        id: this.state.sessionId,
        created_at: this.state.createdAt,
        completed_at: this.state.completedAt,
        turns: this.state.turns,
        report_text: this.state.report,
      }, this.lifetime.signal);
      if (session !== this.session) return;
      if (saved.id !== this.state.sessionId) throw new Error('Saved session ID did not match. Please retry saving.');
      this.update({ phase: 'complete', savedConversation: saved });
    } catch (error) {
      if (session === this.session) this.fail(error, () => this.save(), 'Retry save');
    }
  }

  async retry() {
    if (!this.retryAction || !this.state.retryable) return;
    const action = this.retryAction;
    if (this.state.retryLabel === 'Retry save') {
      await action();
      return;
    }
    this.update({ retryable: false, warning: '', userSpeaking: false, phase: 'listening' });
    try {
      await this.audio.unlock();
      await action();
    } catch (error) { this.fail(error, action); }
  }

  async dispose() {
    this.session += 1;
    this.accepting = false;
    this.lifetime?.abort();
    this.invalidate();
    await this.audio.close();
  }
}
