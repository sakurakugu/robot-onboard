import { Request, Response } from 'express';
import config from '../../config';
import { SettingsService } from './service';

export class SettingsController {
  constructor(private settingsService: SettingsService) {}

  private normalizeParam = (v: unknown): string =>
    Array.isArray(v) ? String(v[0]) : String(v ?? '');

  async getLLMConfig(req: Request, res: Response) {
    try {
      const data = this.settingsService.getLLMConfig();
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getParams(req: Request, res: Response) {
    try {
      const data = this.settingsService.getParamsConfig();
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getLLMProviders(req: Request, res: Response) {
    try {
      const data = this.settingsService.getLLMProviders();
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async updateLLMConfig(req: Request, res: Response) {
    try {
      const data = this.settingsService.updateLLMConfig(req.body || {});
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async updateParams(req: Request, res: Response) {
    try {
      const data = this.settingsService.updateParams(req.body || {});
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getUIConfig(req: Request, res: Response) {
    try {
      const data = this.settingsService.getUIConfig();
      const host = (req.headers.host || '').trim();
      const serverUrl = data.serverUrl && String(data.serverUrl).length > 0 ? data.serverUrl : host;
      const wsPath = data.wsPath && String(data.wsPath).length > 0 ? data.wsPath : '/api/v1/conversation/connect';

      const resolveWsBaseUrl = (input: string, port: number) => {
        const hasScheme = /^https?:\/\//i.test(input);
        const baseUrl = hasScheme ? input : `${req.protocol}://${input}`;
        try {
          const u = new URL(baseUrl);
          const scheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
          return `${scheme}//${u.hostname}:${port}`;
        } catch {
          return `ws://${input}:${port}`;
        }
      };

      const wsControlUrl =
        data.wsControlUrl && String(data.wsControlUrl).length > 0
          ? data.wsControlUrl
          : resolveWsBaseUrl(serverUrl, config.ports.control);
      const wsBusinessUrl =
        data.wsBusinessUrl && String(data.wsBusinessUrl).length > 0
          ? data.wsBusinessUrl
          : resolveWsBaseUrl(serverUrl, config.ports.business);
      const wsAudioUploadUrl =
        data.wsAudioUploadUrl && String(data.wsAudioUploadUrl).length > 0
          ? data.wsAudioUploadUrl
          : resolveWsBaseUrl(serverUrl, config.ports.audioUpload);
      const wsAudioDownloadUrl =
        data.wsAudioDownloadUrl && String(data.wsAudioDownloadUrl).length > 0
          ? data.wsAudioDownloadUrl
          : resolveWsBaseUrl(serverUrl, config.ports.audioDownload);

      res.json({
        success: true,
        data: {
          ...data,
          serverUrl,
          wsPath,
          wsControlUrl,
          wsBusinessUrl,
          wsAudioUploadUrl,
          wsAudioDownloadUrl,
        },
      });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async updateUIConfig(req: Request, res: Response) {
    try {
      this.settingsService.updateUIConfig(req.body || {});
      res.json({ success: true });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async checkUpdate(req: Request, res: Response) {
    try {
      const robotId = this.normalizeParam((req.query as any).robotId);
      const data = this.settingsService.checkUpdate(robotId || undefined);
      res.json({ success: true, data });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async upgradeApp(req: Request, res: Response) {
    try {
      res.json({ success: true, message: '已触发APP升级（预留接口）' });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }
}
