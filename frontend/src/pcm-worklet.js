// AudioWorkletProcessor that converts the mic's Float32 samples to raw
// Int16 PCM and posts blocks back to the main thread. Runs on the audio
// rendering thread, so it must stay dependency-free (no imports, no DOM
// access) -- this file is loaded directly via
// audioContext.audioWorklet.addModule(new URL("./pcm-worklet.js", import.meta.url)).
//
// The AudioContext that owns this worklet is created with
// { sampleRate: 16000 } (see toggleMicrophone() in App.tsx), so samples
// arriving here are already resampled to 16kHz by the browser -- this file
// only needs to do the Float32 -> Int16 conversion, matching what the
// backend expects (audio/pcm;rate=16000, see agent_engine_client.py).
//
// process() fires roughly every 128 samples (~8ms @ 16kHz) -- posting a
// message per call would send ~125 frames/sec, which is unnecessary
// network/message overhead for real-time audio. Buffer samples here and
// flush in ~100ms batches instead (still low enough latency for a live
// conversation).

const FLUSH_THRESHOLD_SAMPLES = 1600; // ~100ms @ 16kHz

class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._chunks = [];
    this._bufferedSamples = 0;
  }

  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];
    if (channel && channel.length) {
      const pcm16 = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, channel[i]));
        pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      this._chunks.push(pcm16);
      this._bufferedSamples += pcm16.length;
      if (this._bufferedSamples >= FLUSH_THRESHOLD_SAMPLES) {
        this._flush();
      }
    }
    return true;
  }

  _flush() {
    if (this._bufferedSamples === 0) return;
    const merged = new Int16Array(this._bufferedSamples);
    let offset = 0;
    for (const chunk of this._chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this._chunks = [];
    this._bufferedSamples = 0;
    this.port.postMessage(merged.buffer, [merged.buffer]);
  }
}

registerProcessor("pcm-worklet-processor", PCMWorkletProcessor);
