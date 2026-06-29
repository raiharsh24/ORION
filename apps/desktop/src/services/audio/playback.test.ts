import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioQueue } from './queue';
import { WebAudioDecoder } from './decoder';
import { PlaybackManager } from './playback';

// Mock Web Audio API classes
class MockAudioBuffer {
  sampleRate = 16000;
  length = 16000;
  duration = 1.0;
  numberOfChannels = 1;
}

class MockAudioBufferSourceNode {
  buffer: any = null;
  onended: (() => void) | null = null;
  connect = vi.fn();
  start = vi.fn().mockImplementation(function(this: MockAudioBufferSourceNode) {
    // Simulate completion on next tick
    setTimeout(() => {
      if (this.onended) this.onended();
    }, 5);
  });
  stop = vi.fn();
}

class MockAudioContext {
  destination = {};
  createBufferSource() {
    return new MockAudioBufferSourceNode();
  }
  decodeAudioData = vi.fn().mockImplementation((buffer: ArrayBuffer) => {
    if (buffer.byteLength === 0) {
      return Promise.reject(new Error("Decode error"));
    }
    return Promise.resolve(new MockAudioBuffer());
  });
}

describe('Voice Audio Playback Subsystem tests', () => {
  let ctx: any;
  let decoder: WebAudioDecoder;
  let queue: AudioQueue;
  let manager: PlaybackManager;

  beforeEach(() => {
    ctx = new MockAudioContext();
    decoder = new WebAudioDecoder(ctx);
    queue = new AudioQueue();
    manager = new PlaybackManager(ctx, decoder, queue, 1);
  });

  it('should successfully enqueue and preserve chunk ordering', async () => {
    const chunk1 = new ArrayBuffer(10);
    const chunk2 = new ArrayBuffer(20);

    // Mock decode to return distinct buffers to verify ordering
    const buffer1 = new MockAudioBuffer();
    const buffer2 = new MockAudioBuffer();
    ctx.decodeAudioData = vi.fn()
      .mockResolvedValueOnce(buffer1)
      .mockResolvedValueOnce(buffer2);

    await manager.handleChunk(chunk1);
    await manager.handleChunk(chunk2);

    // Buffer 1 should be playing first, Buffer 2 remains in queue
    expect(queue.length).toBe(1);
    expect(queue.dequeue()).toBe(buffer2);
  });

  it('should handle queue cleanup on flush', async () => {
    const chunk = new ArrayBuffer(10);
    await manager.handleChunk(chunk);
    
    expect(queue.length).toBe(0); // auto-played immediately
    
    // Add multiple chunks to build queue without triggering play
    vi.spyOn(manager, 'play').mockImplementation(async () => {});
    await manager.handleChunk(chunk);
    await manager.handleChunk(chunk);
    expect(queue.length).toBe(2);

    manager.flush();
    expect(queue.length).toBe(0);
  });

  it('should handle user speech interruption by flushing the queue', async () => {
    const chunk = new ArrayBuffer(10);
    vi.spyOn(manager, 'play').mockImplementation(async () => {});
    await manager.handleChunk(chunk);
    await manager.handleChunk(chunk);
    expect(queue.length).toBe(2);

    manager.interrupt();
    expect(queue.length).toBe(0);
  });

  it('should handle decoder failures gracefully without crashing', async () => {
    const emptyChunk = new ArrayBuffer(0); // Trigger mock decode reject

    await expect(manager.handleChunk(emptyChunk)).rejects.toThrow("Decode error");
    expect(queue.length).toBe(0);
  });

  it('should manage play/stop lifecycle correctly', async () => {
    const chunk = new ArrayBuffer(10);
    const mockSourceNode = new MockAudioBufferSourceNode();
    ctx.createBufferSource = vi.fn().mockReturnValue(mockSourceNode);

    await manager.handleChunk(chunk); // triggers play automatically

    expect(mockSourceNode.start).toHaveBeenCalled();

    manager.stop();
    expect(mockSourceNode.stop).toHaveBeenCalled();
  });
});
