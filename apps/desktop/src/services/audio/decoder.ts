export interface AudioDecoder {
  decode(chunk: ArrayBuffer): Promise<AudioBuffer>;
}

export class WebAudioDecoder implements AudioDecoder {
  private ctx: AudioContext;

  constructor(ctx: AudioContext) {
    this.ctx = ctx;
  }

  async decode(chunk: ArrayBuffer): Promise<AudioBuffer> {
    try {
      // slice the buffer to prevent decodeAudioData from mutating original in some browsers
      const buffer = chunk.slice(0);
      return await this.ctx.decodeAudioData(buffer);
    } catch (e) {
      console.error("WebAudioDecoder: failed to decode audio chunk", e);
      throw e;
    }
  }
}
