export const initialState = () => ({
  phase: 'idle', turns: [], report: '', title: '', speaking: false,
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
    this.delivery = null;
    this.interrupted = null;
    this.opening = false;
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
    this.delivery = null;
    this.interrupted = null;
    this.opening = false;
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
    const delivery = this.delivery;
    const wasSpeaking = this.state.speaking;
    const wasThinking = this.state.phase === 'thinking';
    this.invalidate();
    if (delivery && (wasSpeaking || wasThinking)) {
      // Keep the reply so a cough or other noise can put it back on screen and
      // audio where the learner cut in.
      this.interrupted = {
        delivery, offset: wasSpeaking ? this.audio.lastOffset : null, opening: this.opening,
      };
    }
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
        const text = (result.text || '').trim();
        const seconds = typeof wav?.byteLength === 'number'
          ? Math.max(0, (wav.byteLength - 44) / 32000) : null;
        const unsure = !text || (result.no_speech_prob ?? 0) > 0.6;

        if (result.is_farewell && text) {
          this.interrupted = null;
          this.addTurn(text);
          this.accepting = false;
          this.queue = [];
          this.needsReply = false;
          this.invalidate();
          this.update({ userSpeaking: false });
          await this.audio.pauseInput();
          await this.respond(false, true);
          return;
        }

        if (farewellOnly) {
          // A brief capture that never confirmed as speech. Only a confident
          // phrase heard while nothing is playing may become a turn.
          if (unsure || this.state.phase !== 'listening') continue;
          this.interrupted = null;
          this.addTurn(text);
          continue;
        }

        if (unsure) {
          if (this.interrupted) {
            // What stopped the reply was noise, not a turn. Resume it where the
            // learner cut in rather than leaving the reply half spoken.
            const { delivery, offset, opening } = this.interrupted;
            this.interrupted = null;
            delivery.offset = offset ?? 0;
            delivery.resuming = true;
            await this.respond(opening, false, delivery);
            continue;
          }
          // A very short burst that the recogniser could not use is noise, not
          // a failed turn. Do not nag about every cough.
          if (!text && seconds !== null && seconds < 0.6) continue;
          this.update({ warning: "I didn’t catch that—please try again." });
          continue;
        }

        this.interrupted = null;
        this.addTurn(text);
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

  addTurn(text) {
    this.update({ turns: [...this.state.turns, {
      id: crypto.randomUUID(), role: 'user', text, interrupted: false,
    }], warning: '' });
    this.needsReply = true;
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
    if (!cached) this.interrupted = null;
    delivery.offset ??= 0;
    if (!report) {
      this.delivery = delivery;
      this.opening = opening;
    }
    this.update({ phase: report ? 'preparing-feedback' : 'thinking', warning: '', retryable: false });
    try {
      if (!delivery.text) {
        const result = await this.api[report ? 'report' : 'reply']({ request_id, opening, turns: this.state.turns }, controller.signal);
        if (!current()) return;
        if (result.request_id !== request_id) throw new Error('Received an outdated response. Please retry.');
        delivery.text = report ? result.report_text : result.text;
        if (report) this.update({ report: delivery.text, title: result.title || '' });
      }
      if (report && !delivery.savePromise) {
        if (!this.state.completedAt) this.update({ completedAt: new Date().toISOString() });
        // Persist now, not after the feedback audio. A refresh during playback
        // must not lose the finished conversation.
        delivery.savePromise = this.persist().then(saved => ({ saved }), error => ({ error }));
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
            if (delivery.resuming && delivery.turnId) {
              // The turn is already in the transcript, only paused part-way.
              this.playingTurn = delivery.turnId;
              this.update({ turns: this.state.turns.map(turn => turn.id === delivery.turnId
                ? { ...turn, interrupted: false } : turn) });
            } else {
              this.playingTurn = crypto.randomUUID();
              delivery.turnId = this.playingTurn;
              this.update({ turns: [...this.state.turns, {
                id: this.playingTurn, role: 'assistant', text: delivery.text, interrupted: false,
              }] });
            }
            delivery.resuming = false;
            delivery.offset = 0;
          }
          this.update({ phase: report ? 'feedback-speaking' : 'speaking', speaking: true });
        }, delivery.offset);
        if (!current()) return;
        this.playingTurn = null;
        this.update({ speaking: false });
        if (result !== 'ended') return;
        delivery.index += 1;
        delivery.audio = null;
        delivery.turnId = null;
        delivery.offset = 0;
        if (report && delivery.index < delivery.chunks.length && !delivery.next) {
          this.update({ phase: 'preparing-feedback' });
        }
      }
      if (report) {
        await this.audio.close();
        if (!current()) return;
        const persisted = await delivery.savePromise;
        if (persisted?.error) {
          this.fail(persisted.error, () => this.save(), 'Retry save');
          return;
        }
        if (!persisted?.saved) {
          await this.save();
          return;
        }
        this.update({ phase: 'complete', savedConversation: persisted.saved });
      } else {
        this.delivery = null;
        this.update({ phase: 'listening' });
      }
    } catch (error) {
      if (current()) this.fail(error, () => this.respond(opening, report, delivery));
    }
  }

  async persist() {
    const body = {
      id: this.state.sessionId,
      created_at: this.state.createdAt,
      completed_at: this.state.completedAt,
      title: this.state.title,
      turns: this.state.turns,
      report_text: this.state.report,
    };
    // Do not tie the write to the page lifetime: refreshing while the feedback
    // is spoken should not throw away a finished conversation.
    const saved = await this.api.save(body);
    if (saved.id !== body.id) throw new Error('Saved session ID did not match. Please retry saving.');
    return saved;
  }

  async save() {
    const session = this.session;
    this.update({ phase: 'saving', warning: '', retryable: false });
    try {
      const saved = await this.persist();
      if (session !== this.session) return;
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

  async reset() {
    this.session += 1;
    this.accepting = false;
    this.lifetime?.abort();
    this.lifetime = null;
    this.queue = [];
    this.draining = false;
    this.needsReply = false;
    this.delivery = null;
    this.interrupted = null;
    this.opening = false;
    this.retryAction = null;
    this.invalidate();
    await this.audio.close().catch(() => {});
    this.state = initialState();
    this.publish(this.state);
  }

  async dispose() {
    this.session += 1;
    this.accepting = false;
    this.lifetime?.abort();
    this.invalidate();
    await this.audio.close();
  }
}
