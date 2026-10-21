export const initialState = () => ({
  phase: 'idle', turns: [], report: '', speaking: false,
  userSpeaking: false, warning: '', retryable: false, sessionId: null,
});

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
      await this.audio.listen({
        onSpeechStart: () => this.speechStart(),
        onSpeechEnd: (wav, options) => this.speechEnd(wav, options),
      });
      if (session !== this.session) return;
      this.accepting = true;
      await this.respond(true);
    } catch (error) {
      if (session !== this.session) return;
      await this.audio.close();
      this.fail(error, () => this.start());
    }
  }

  fail(error, retry) {
    if (error.name === 'AbortError') return;
    this.retryAction = retry;
    this.update({ phase: 'error', speaking: false, warning: error.message, retryable: true });
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

  async respond(opening, report = false, cachedText = null) {
    this.invalidate();
    const generation = this.generation;
    const session = this.session;
    const controller = new AbortController();
    this.pending = controller;
    const current = () => session === this.session && generation === this.generation && !controller.signal.aborted;
    const request_id = `${this.state.sessionId}:${generation}`;
    let text = cachedText;
    this.update({ phase: report ? 'preparing-feedback' : 'thinking', warning: '', retryable: false });
    try {
      if (!text) {
        const result = await this.api[report ? 'report' : 'reply']({ request_id, opening, turns: this.state.turns }, controller.signal);
        if (!current()) return;
        if (result.request_id !== request_id) throw new Error('Received an outdated response. Please retry.');
        text = report ? result.report_text : result.text;
        if (report) this.update({ report: text });
      }
      const bytes = await this.api.speech({ request_id, text }, controller.signal);
      if (!current()) return;
      const result = await this.audio.play(bytes, current, () => {
        if (!current()) return;
        if (!report) {
          this.playingTurn = crypto.randomUUID();
          this.update({ turns: [...this.state.turns, {
            id: this.playingTurn, role: 'assistant', text, interrupted: false,
          }] });
        }
        this.update({ phase: report ? 'feedback-speaking' : 'speaking', speaking: true });
      });
      if (!current()) return;
      this.playingTurn = null;
      this.update({ speaking: false });
      if (result !== 'ended') return;
      if (report) {
        await this.audio.close();
        if (current()) this.update({ phase: 'complete', completedAt: new Date().toISOString() });
      } else {
        this.update({ phase: 'listening' });
      }
    } catch (error) {
      if (current()) this.fail(error, () => this.respond(opening, report, text));
    }
  }

  async retry() {
    if (!this.retryAction || !this.state.retryable) return;
    const action = this.retryAction;
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
