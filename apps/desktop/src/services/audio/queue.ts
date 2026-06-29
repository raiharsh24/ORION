export class AudioQueue {
  private queue: AudioBuffer[] = [];
  private onReadyCallbacks: (() => void)[] = [];

  enqueue(buffer: AudioBuffer): void {
    this.queue.push(buffer);
    this.triggerReady();
  }

  dequeue(): AudioBuffer | null {
    if (this.queue.length === 0) {
      return null;
    }
    return this.queue.shift() || null;
  }

  get length(): number {
    return this.queue.length;
  }

  clear(): void {
    this.queue = [];
    this.onReadyCallbacks = [];
  }

  async waitForNext(): Promise<AudioBuffer> {
    if (this.queue.length > 0) {
      return this.queue.shift()!;
    }
    return new Promise<AudioBuffer>((resolve) => {
      this.onReadyCallbacks.push(() => {
        resolve(this.queue.shift()!);
      });
    });
  }

  private triggerReady(): void {
    if (this.onReadyCallbacks.length > 0 && this.queue.length > 0) {
      const cb = this.onReadyCallbacks.shift();
      if (cb) cb();
    }
  }
}
