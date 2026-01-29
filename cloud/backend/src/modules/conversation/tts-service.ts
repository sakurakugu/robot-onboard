import { spawn } from 'child_process';
import path from 'path';
import { AudioResponse, TTSOptions } from '../../types';

class TTSService {
  constructor() {}

  async synthesize(text: string, options?: TTSOptions): Promise<AudioResponse> {
    const scriptPath = path.join(__dirname, '../../core/scripts/edge_tts_runner.py');
    return new Promise<AudioResponse>((resolve, reject) => {
      const proc = spawn('python3', [scriptPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      const payload = {
        text,
        voice: options?.voice || 'zh-CN-XiaoxiaoNeural',
        speed: options?.speed ?? 0,
        pitch: options?.pitch ?? 0,
        volume: options?.volume ?? 0,
      };

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (d) => (stdout += d.toString()));
      proc.stderr.on('data', (d) => (stderr += d.toString()));

      proc.on('error', (err) => reject(err));
      proc.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(stderr || `edge-tts 意外退出，代码 ${code}`));
          return;
        }
        try {
          const result = JSON.parse(stdout);
          resolve({
            format: (result.format as any) || 'mp3',
            buffer: result.base64,
            duration: result.duration || 0,
          });
        } catch (e) {
          reject(e);
        }
      });

      proc.stdin.write(JSON.stringify(payload));
      proc.stdin.end();
    });
  }
}

export default TTSService;
