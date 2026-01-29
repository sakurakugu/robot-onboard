import axios from 'axios';
import crypto from 'crypto';
import FormData from 'form-data';
import WebSocket from 'ws';
import config from '../../config';

export interface ASROptions {
  language?: string;
  prompt?: string;
}

class ASRService {
  async transcribeWav(wavBuffer: Buffer, options?: ASROptions): Promise<string> {
    const provider = config.asr.provider;
    switch (provider) {
      case 'xunfei':
        return this.transcribeXunfei(wavBuffer, options);
      case 'openai':
        return this.transcribeOpenAI(wavBuffer, options);
      default:
        throw new Error(`不支持的ASR提供商: ${provider}`);
    }
  }

  private async transcribeXunfei(wavBuffer: Buffer, options?: ASROptions): Promise<string> {
    const xunfei = config.asr.xunfei;
    if (!xunfei?.appId || !xunfei.apiKey || !xunfei.apiSecret) {
      throw new Error('讯飞ASR密钥未配置');
    }

    const host = 'iat-api.xfyun.cn';
    const path = '/v2/iat';
    const url = this.buildXunfeiUrl(host, path, xunfei.apiKey, xunfei.apiSecret);

    const pcmBuffer = this.extractPcmFromWav(wavBuffer);
    const sampleRate = this.detectSampleRate(wavBuffer) || 16000;
    const frameSize = 1280;
    const intervalMs = 40;

    const language = options?.language || 'zh_cn';

    return new Promise<string>((resolve, reject) => {
      const ws = new WebSocket(url);
      let closed = false;
      let finalText = '';

      const cleanup = () => {
        if (closed) return;
        closed = true;
        try {
          ws.close();
        } catch {}
      };

      ws.on('open', async () => {
        try {
          let status = 0;
          for (let offset = 0; offset < pcmBuffer.length; offset += frameSize) {
            const chunk = pcmBuffer.slice(offset, offset + frameSize);
            const payload: any = {
              data: {
                status,
                format: `audio/L16;rate=${sampleRate}`,
                encoding: 'raw',
                audio: chunk.toString('base64'),
              },
            };
            if (status === 0) {
              payload.common = { app_id: xunfei.appId };
              payload.business = {
                language,
                domain: 'iat',
                accent: 'mandarin',
                vad_eos: 2000,
                ptt: 1,
              };
              status = 1;
            }

            ws.send(JSON.stringify(payload));
            await new Promise(r => setTimeout(r, intervalMs));
          }

          const endPayload = { data: { status: 2 } };
          ws.send(JSON.stringify(endPayload));
        } catch (err) {
          cleanup();
          reject(err);
        }
      });

      ws.on('message', (data: WebSocket.RawData) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.code !== 0) {
            cleanup();
            reject(new Error(msg.message || `讯飞ASR错误: ${msg.code}`));
            return;
          }

          const wsResults = msg?.data?.result?.ws || [];
          if (Array.isArray(wsResults)) {
            const textPart = wsResults
              .map((w: any) => w?.cw?.[0]?.w || '')
              .join('');
            finalText += textPart;
          }

          if (msg?.data?.status === 2) {
            cleanup();
            resolve(finalText.trim());
          }
        } catch (err) {
          cleanup();
          reject(err);
        }
      });

      ws.on('error', (err) => {
        cleanup();
        reject(err);
      });

      ws.on('close', () => {
        if (!closed) {
          closed = true;
          resolve(finalText.trim());
        }
      });
    });
  }

  private buildXunfeiUrl(host: string, path: string, apiKey: string, apiSecret: string): string {
    const date = new Date().toUTCString();
    const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
    const signatureSha = crypto
      .createHmac('sha256', apiSecret)
      .update(signatureOrigin)
      .digest('base64');

    const authorizationOrigin = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signatureSha}"`;
    const authorization = Buffer.from(authorizationOrigin).toString('base64');

    const params = new URLSearchParams({
      authorization,
      date,
      host,
    });
    return `wss://${host}${path}?${params.toString()}`;
  }

  private extractPcmFromWav(wavBuffer: Buffer): Buffer {
    if (wavBuffer.length < 44) return wavBuffer;
    if (wavBuffer.toString('ascii', 0, 4) !== 'RIFF') return wavBuffer;
    if (wavBuffer.toString('ascii', 8, 12) !== 'WAVE') return wavBuffer;

    let offset = 12;
    while (offset + 8 <= wavBuffer.length) {
      const chunkId = wavBuffer.toString('ascii', offset, offset + 4);
      const chunkSize = wavBuffer.readUInt32LE(offset + 4);
      if (chunkId === 'data') {
        return wavBuffer.slice(offset + 8, offset + 8 + chunkSize);
      }
      offset += 8 + chunkSize;
    }
    return wavBuffer;
  }

  private detectSampleRate(wavBuffer: Buffer): number | null {
    if (wavBuffer.length < 28) return null;
    if (wavBuffer.toString('ascii', 0, 4) !== 'RIFF') return null;
    return wavBuffer.readUInt32LE(24);
  }

  private async transcribeOpenAI(wavBuffer: Buffer, options?: ASROptions): Promise<string> {
    const openai = config.asr.openai;
    if (!openai?.apiKey) {
      throw new Error('OpenAI ASR API密钥未配置');
    }

    const url = `${openai.baseUrl || 'https://api.openai.com/v1'}/audio/transcriptions`;
    const form = new FormData();
    form.append('model', openai.model || 'whisper-1');
    form.append('file', wavBuffer, {
      filename: 'audio.wav',
      contentType: 'audio/wav',
    });

    const language = options?.language || openai.language || '';
    if (language) {
      form.append('language', language);
    }
    const prompt = options?.prompt || openai.prompt || '';
    if (prompt) {
      form.append('prompt', prompt);
    }

    try {
      const response = await axios.post(url, form, {
        headers: {
          ...form.getHeaders(),
          Authorization: `Bearer ${openai.apiKey}`,
        },
        maxBodyLength: Infinity,
        timeout: 60000,
      });
      const text = String(response.data?.text || '').trim();
      return text;
    } catch (error: any) {
      const data = error.response?.data;
      const message = data?.error?.message || data?.message || error.message;
      throw new Error(`ASR调用失败: ${message}`);
    }
  }
}

export default ASRService;
