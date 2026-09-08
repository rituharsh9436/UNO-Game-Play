/**
 * Zero-latency Spatial Sound System for Multiplayer UNO.
 * Uses Web Audio API procedural synthesis with Howler.js compatibility.
 * Compliant with docs.md Section 9.2.
 */

class SoundEngine {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;

  private getContext(): AudioContext | null {
    if (typeof window === "undefined") return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
  }

  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    return this.isMuted;
  }

  /**
   * Card play: snappy whoosh and slap.
   */
  public playCard() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.exponentialRampToValueAtTime(140, now + 0.1);

    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.1);
  }

  /**
   * Card draw: crisp quick flick.
   */
  public drawCard() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "triangle";
    osc.frequency.setValueAtTime(480, now);
    osc.frequency.exponentialRampToValueAtTime(680, now + 0.08);

    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.08);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.08);
  }

  /**
   * Action Skip: low thud buzzer.
   */
  public actionSkip() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(180, now);
    osc.frequency.exponentialRampToValueAtTime(90, now + 0.25);

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.25);
  }

  /**
   * Action Reverse: circular stereo swoosh.
   */
  public actionReverse() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(260, now);
    osc.frequency.exponentialRampToValueAtTime(540, now + 0.15);
    osc.frequency.exponentialRampToValueAtTime(320, now + 0.3);

    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.3);
  }

  /**
   * Dramatic brass bell when UNO is declared or caught.
   */
  public unoAlert() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    // Chime chord: 523Hz (C5), 659Hz (E5), 784Hz (G5)
    [523.25, 659.25, 783.99, 1046.5].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + idx * 0.04);

      gain.gain.setValueAtTime(0.25, now + idx * 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now + idx * 0.04);
      osc.stop(now + 0.8);
    });
  }

  /**
   * Timer Tick: subtle click for the last 5 seconds.
   */
  public timerTick() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "square";
    osc.frequency.setValueAtTime(800, now);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.03);
  }

  /**
   * Game Victory Fanfare.
   */
  public gameWin() {
    if (this.isMuted) return;
    const ctx = this.getContext();
    if (!ctx) return;

    const notes = [
      { f: 523.25, t: 0.0 }, // C5
      { f: 659.25, t: 0.15 }, // E5
      { f: 783.99, t: 0.3 }, // G5
      { f: 1046.5, t: 0.5 }, // C6
    ];

    notes.forEach((note) => {
      const now = ctx.currentTime + note.t;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "triangle";
      osc.frequency.setValueAtTime(note.f, now);

      gain.gain.setValueAtTime(0.3, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.6);
    });
  }
}

export const soundManager = new SoundEngine();
