// AudioWorkletProcessor that converts the mic's Float32 samples to raw
// Int16 PCM and posts each block back to the main thread. Runs on the
// audio rendering thread, so it must stay dependency-free (no imports,
// no DOM access) -- this file is loaded directly via
// audioContext.audioWorklet.addModule(new URL("./pcm-worklet.js", import.meta.url)).
//
// The AudioContext that owns this worklet is created with
// { sampleRate: 16000 } (see toggleMicrophone() in App.tsx), so samples
// arriving here are already resampled to 16kHz by the browser -- this file
// only needs to do the Float32 -> Int16 conversion, matching what the
// backend expects (audio/pcm;rate=16000, see agent_engine_client.py).

class PCMWorkletProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];
    if (channel && channel.length) {
      const pcm16 = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, channel[i]));
        pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-worklet-processor", PCMWorkletProcessor);
