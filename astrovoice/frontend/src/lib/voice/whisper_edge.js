import { pipeline } from '@xenova/transformers';

class WhisperEdge {
    constructor() {
        this.processor = null;
        this.model = null;
        this.initialized = false;
    }

    async init() {
        if (this.initialized) return;
        
        // Load Whisper Tiny ONNX model
        this.transcriber = await pipeline('automatic-speech-recognition', 'Xenova/whisper-tiny.en', {
            device: 'webgpu', // Fallback to cpu if not available
        });
        
        this.initialized = true;
    }

    async transcribe(audioBuffer) {
        if (!this.initialized) await this.init();
        
        const output = await this.transcriber(audioBuffer, {
            chunk_length_s: 30,
            stride_length_s: 5,
        });
        
        return output.text;
    }
}

export const whisperEdge = new WhisperEdge();
