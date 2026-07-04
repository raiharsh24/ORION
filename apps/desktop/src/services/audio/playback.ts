import type { AudioDecoder } from './decoder';
import { AudioQueue } from './queue';

export class PlaybackManager {
  private ctx: AudioContext;
  private decoder: AudioDecoder;
  private queue: AudioQueue;
  private isPlaying = false;
  private currentSourceNode: AudioBufferSourceNode | null = null;
  private minBufferedChunks: number;

  constructor(ctx: AudioContext, decoder: AudioDecoder, queue: AudioQueue, minBufferedChunks = 1) {
    this.ctx = ctx;
    this.decoder = decoder;
    this.queue = queue;
    this.minBufferedChunks = minBufferedChunks;
  }

  async handleChunk(chunk: ArrayBuffer): Promise<void> {
    try {
      const decoded = await this.decoder.decode(chunk);
      this.queue.enqueue(decoded);
      
      // Auto-start playout if threshold met and not already playing
      if (!this.isPlaying && this.queue.length >= this.minBufferedChunks) {
        this.play();
      }
    } catch (e) {
      console.error("PlaybackManager: failed to decode/enqueue chunk", e);
      throw e;
    }
  }

  async play(): Promise<void> {
    if (this.isPlaying) return;
    this.isPlaying = true;
    this.playLoop();
  }

  private async playLoop(): Promise<void> {
    while (this.isPlaying) {
      if (this.queue.length === 0) {
        // Wait for next chunk to avoid underflow
        try {
          const nextBuffer = await this.queue.waitForNext();
          await this.playBuffer(nextBuffer);
        } catch (e) {
          console.error("PlaybackManager: loop aborted", e);
          break;
        }
      } else {
        const nextBuffer = this.queue.dequeue();
        if (nextBuffer) {
          await this.playBuffer(nextBuffer);
        }
      }
    }
  }

  private playBuffer(buffer: AudioBuffer): Promise<void> {
    return new Promise<void>((resolve) => {
      if (!this.isPlaying) {
        resolve();
        return;
      }

      try {
        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(this.ctx.destination);
        this.currentSourceNode = source;

        source.onended = () => {
          if (this.currentSourceNode === source) {
            this.currentSourceNode = null;
          }
          resolve();
        };

        source.start(0);
      } catch (err) {
        console.error("PlaybackManager: error playing source node", err);
        resolve();
      }
    });
  }

  stop(): void {
    this.isPlaying = false;
    if (this.currentSourceNode) {
      try {
        this.currentSourceNode.stop();
      } catch (e) {
        // Source already stopped or not started
      }
      this.currentSourceNode = null;
    }
  }

  flush(): void {
    this.stop();
    this.queue.clear();
  }

  interrupt(): void {
    logger.info("PlaybackManager: interruption triggered, flushing stream.");
    this.flush();
  }
}

// Global logger helper fallback
const logger = {
  info: (msg: string) => console.log(msg)
};
