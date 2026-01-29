import config from '../../config';
import { LLM_PROVIDERS } from '../../config/llm-providers';
import DatabaseService from '../../core/database';

export class SettingsService {
  constructor(private database: DatabaseService) {}

  getParamsConfig() {
    const provider = this.database.getParam('llm.provider') || '';
    const openaiKey = this.database.getParam('openai.apiKey') || '';
    const openaiModel = this.database.getParam('openai.model') || '';
    const openaiBaseUrl = this.database.getParam('openai.baseUrl') || '';
    const bigKey = this.database.getParam('bigmodel.apiKey') || '';
    const bigModel = this.database.getParam('bigmodel.model') || '';
    const bigBaseUrl = this.database.getParam('bigmodel.baseUrl') || '';
    const anthropicKey = this.database.getParam('anthropic.apiKey') || '';
    const anthropicModel = this.database.getParam('anthropic.model') || '';
    const anthropicBaseUrl = this.database.getParam('anthropic.baseUrl') || '';
    const deepseekKey = this.database.getParam('deepseek.apiKey') || '';
    const deepseekModel = this.database.getParam('deepseek.model') || '';
    const deepseekBaseUrl = this.database.getParam('deepseek.baseUrl') || '';

    return {
      provider,
      openai: {
        model: openaiModel,
        baseUrl: openaiBaseUrl,
        hasApiKey: !!(openaiKey && String(openaiKey).length > 0),
        apiKeyLength: openaiKey ? String(openaiKey).length : 0
      },
      bigmodel: {
        model: bigModel,
        baseUrl: bigBaseUrl,
        hasApiKey: !!(bigKey && String(bigKey).length > 0),
        apiKeyLength: bigKey ? String(bigKey).length : 0
      },
      anthropic: {
        model: anthropicModel,
        baseUrl: anthropicBaseUrl,
        hasApiKey: !!(anthropicKey && String(anthropicKey).length > 0),
        apiKeyLength: anthropicKey ? String(anthropicKey).length : 0
      },
      deepseek: {
        model: deepseekModel,
        baseUrl: deepseekBaseUrl,
        hasApiKey: !!(deepseekKey && String(deepseekKey).length > 0),
        apiKeyLength: deepseekKey ? String(deepseekKey).length : 0
      }
    };
  }

  getLLMConfig() {
    const provider = config.llm.provider;
    const openai = config.llm.openai;
    const bigmodel = config.llm.bigmodel;
    
    // 获取所有服务商的配置
    const allConfigs: any = {
      provider
    };

    // OpenAI
    allConfigs.openai = {
      model: openai?.model || '',
      baseUrl: openai?.baseUrl || '',
      hasApiKey: !!(openai?.apiKey && String(openai.apiKey).length > 0),
      apiKeyLength: openai?.apiKey ? String(openai.apiKey).length : 0
    };

    // BigModel
    allConfigs.bigmodel = {
      model: bigmodel?.model || '',
      baseUrl: bigmodel?.baseUrl || '',
      hasApiKey: !!(bigmodel?.apiKey && String(bigmodel.apiKey).length > 0),
      apiKeyLength: bigmodel?.apiKey ? String(bigmodel.apiKey).length : 0
    };

    // Anthropic (如果有的话)
    const anthropicApiKey = this.database.getSetting('anthropic.apiKey');
    const anthropicModel = this.database.getSetting('anthropic.model');
    const anthropicBaseUrl = this.database.getSetting('anthropic.baseUrl');
    allConfigs.anthropic = {
      model: anthropicModel || '',
      baseUrl: anthropicBaseUrl || '',
      hasApiKey: !!(anthropicApiKey && String(anthropicApiKey).length > 0),
      apiKeyLength: anthropicApiKey ? String(anthropicApiKey).length : 0
    };

    // DeepSeek (如果有的话)
    const deepseekApiKey = this.database.getSetting('deepseek.apiKey');
    const deepseekModel = this.database.getSetting('deepseek.model');
    const deepseekBaseUrl = this.database.getSetting('deepseek.baseUrl');
    allConfigs.deepseek = {
      model: deepseekModel || '',
      baseUrl: deepseekBaseUrl || '',
      hasApiKey: !!(deepseekApiKey && String(deepseekApiKey).length > 0),
      apiKeyLength: deepseekApiKey ? String(deepseekApiKey).length : 0
    };
    
    return allConfigs;
  }

  getLLMProviders() {
    return LLM_PROVIDERS;
  }

  updateParams(data: {
    provider?: string;
    openai?: { apiKey?: string; model?: string; baseUrl?: string };
    bigmodel?: { apiKey?: string; model?: string; baseUrl?: string };
    anthropic?: { apiKey?: string; model?: string; baseUrl?: string };
    deepseek?: { apiKey?: string; model?: string; baseUrl?: string };
  }) {
    if (typeof data.provider === 'string' && data.provider.length > 0) {
      this.database.setParam('llm.provider', data.provider);
      this.database.setSetting('llm.provider', data.provider);
      (config.llm as any).provider = data.provider as any;
    }
    if (data.openai) {
      if (typeof data.openai.apiKey === 'string') {
        this.database.setParam('openai.apiKey', data.openai.apiKey);
        this.database.setSetting('openai.apiKey', data.openai.apiKey);
        config.llm.openai = config.llm.openai || { apiKey: '', model: '' };
        config.llm.openai.apiKey = data.openai.apiKey;
      }
      if (typeof data.openai.model === 'string') {
        this.database.setParam('openai.model', data.openai.model);
        this.database.setSetting('openai.model', data.openai.model);
        config.llm.openai = config.llm.openai || { apiKey: '', model: '' };
        config.llm.openai.model = data.openai.model;
      }
      if (typeof data.openai.baseUrl === 'string') {
        this.database.setParam('openai.baseUrl', data.openai.baseUrl || '');
        this.database.setSetting('openai.baseUrl', data.openai.baseUrl || '');
        config.llm.openai = config.llm.openai || { apiKey: '', model: '' };
        config.llm.openai.baseUrl = data.openai.baseUrl || undefined;
      }
    }
    if (data.bigmodel) {
      if (typeof data.bigmodel.apiKey === 'string') {
        this.database.setParam('bigmodel.apiKey', data.bigmodel.apiKey);
        this.database.setSetting('bigmodel.apiKey', data.bigmodel.apiKey);
        config.llm.bigmodel = config.llm.bigmodel || { apiKey: '', model: '' };
        config.llm.bigmodel.apiKey = data.bigmodel.apiKey;
      }
      if (typeof data.bigmodel.model === 'string') {
        this.database.setParam('bigmodel.model', data.bigmodel.model);
        this.database.setSetting('bigmodel.model', data.bigmodel.model);
        config.llm.bigmodel = config.llm.bigmodel || { apiKey: '', model: '' };
        config.llm.bigmodel.model = data.bigmodel.model;
      }
      if (typeof data.bigmodel.baseUrl === 'string') {
        this.database.setParam('bigmodel.baseUrl', data.bigmodel.baseUrl || '');
        this.database.setSetting('bigmodel.baseUrl', data.bigmodel.baseUrl || '');
        config.llm.bigmodel = config.llm.bigmodel || { apiKey: '', model: '' };
        config.llm.bigmodel.baseUrl = data.bigmodel.baseUrl || undefined;
      }
    }
    if (data.anthropic) {
      if (typeof data.anthropic.apiKey === 'string') {
        this.database.setParam('anthropic.apiKey', data.anthropic.apiKey);
        this.database.setSetting('anthropic.apiKey', data.anthropic.apiKey);
      }
      if (typeof data.anthropic.model === 'string') {
        this.database.setParam('anthropic.model', data.anthropic.model);
        this.database.setSetting('anthropic.model', data.anthropic.model);
      }
      if (typeof data.anthropic.baseUrl === 'string') {
        this.database.setParam('anthropic.baseUrl', data.anthropic.baseUrl || '');
        this.database.setSetting('anthropic.baseUrl', data.anthropic.baseUrl || '');
      }
    }
    if (data.deepseek) {
      if (typeof data.deepseek.apiKey === 'string') {
        this.database.setParam('deepseek.apiKey', data.deepseek.apiKey);
        this.database.setSetting('deepseek.apiKey', data.deepseek.apiKey);
      }
      if (typeof data.deepseek.model === 'string') {
        this.database.setParam('deepseek.model', data.deepseek.model);
        this.database.setSetting('deepseek.model', data.deepseek.model);
      }
      if (typeof data.deepseek.baseUrl === 'string') {
        this.database.setParam('deepseek.baseUrl', data.deepseek.baseUrl || '');
        this.database.setSetting('deepseek.baseUrl', data.deepseek.baseUrl || '');
      }
    }
    return { success: true };
  }

  updateLLMConfig(data: {
    provider?: string;
    apiKey?: string;
    model?: string;
    baseUrl?: string;
  }) {
    const validProviders = ['openai', 'bigmodel', 'anthropic', 'deepseek'];
    const finalProvider = validProviders.includes(data.provider || '') 
      ? data.provider 
      : config.llm.provider;
    
    config.llm.provider = finalProvider as any;
    this.database.setSetting('llm.provider', finalProvider as string);

    // 根据服务商保存配置
    if (finalProvider === 'openai') {
      config.llm.openai = config.llm.openai || { apiKey: '', model: '' };
      if (typeof data.apiKey === 'string') {
        config.llm.openai.apiKey = data.apiKey;
        this.database.setSetting('openai.apiKey', data.apiKey);
      }
      if (typeof data.model === 'string') {
        config.llm.openai.model = data.model;
        this.database.setSetting('openai.model', data.model);
      }
      if (typeof data.baseUrl === 'string') {
        config.llm.openai.baseUrl = data.baseUrl || undefined;
        this.database.setSetting('openai.baseUrl', data.baseUrl || '');
      }
    } else if (finalProvider === 'bigmodel') {
      config.llm.bigmodel = config.llm.bigmodel || { apiKey: '', model: '' };
      if (typeof data.apiKey === 'string') {
        config.llm.bigmodel.apiKey = data.apiKey;
        this.database.setSetting('bigmodel.apiKey', data.apiKey);
      }
      if (typeof data.model === 'string') {
        config.llm.bigmodel.model = data.model;
        this.database.setSetting('bigmodel.model', data.model);
      }
      if (typeof data.baseUrl === 'string') {
        config.llm.bigmodel.baseUrl = data.baseUrl || undefined;
        this.database.setSetting('bigmodel.baseUrl', data.baseUrl || '');
      }
    } else if (finalProvider === 'anthropic') {
      if (typeof data.apiKey === 'string') {
        this.database.setSetting('anthropic.apiKey', data.apiKey);
      }
      if (typeof data.model === 'string') {
        this.database.setSetting('anthropic.model', data.model);
      }
      if (typeof data.baseUrl === 'string') {
        this.database.setSetting('anthropic.baseUrl', data.baseUrl || '');
      }
    } else if (finalProvider === 'deepseek') {
      if (typeof data.apiKey === 'string') {
        this.database.setSetting('deepseek.apiKey', data.apiKey);
      }
      if (typeof data.model === 'string') {
        this.database.setSetting('deepseek.model', data.model);
      }
      if (typeof data.baseUrl === 'string') {
        this.database.setSetting('deepseek.baseUrl', data.baseUrl || '');
      }
    }

    return { provider: config.llm.provider };
  }

  getUIConfig() {
    const serverUrl = this.database.getSetting('ui.serverUrl') || '';
    const wsPath = this.database.getSetting('ui.wsPath') || config.ws.path || '/api/v1/conversation/connect';
    const wsControlUrl = this.database.getSetting('ui.wsControlUrl') || '';
    const wsBusinessUrl = this.database.getSetting('ui.wsBusinessUrl') || '';
    const wsAudioUploadUrl = this.database.getSetting('ui.wsAudioUploadUrl') || '';
    const wsAudioDownloadUrl = this.database.getSetting('ui.wsAudioDownloadUrl') || '';
    const mhRaw = this.database.getSetting('ui.maxHistory');
    const maxHistory = mhRaw ? parseInt(mhRaw, 10) || 10 : 10;
    const layoutRaw = this.database.getSetting('ui.controlLayout');
    let controlLayout: any = null;
    if (layoutRaw) {
      try {
        controlLayout = JSON.parse(layoutRaw);
      } catch {
        controlLayout = null;
      }
    }
    
    return {
      serverUrl,
      wsPath,
      wsControlUrl,
      wsBusinessUrl,
      wsAudioUploadUrl,
      wsAudioDownloadUrl,
      maxHistory,
      controlLayout,
    };
  }

  updateUIConfig(data: {
    serverUrl?: string;
    wsPath?: string;
    wsControlUrl?: string;
    wsBusinessUrl?: string;
    wsAudioUploadUrl?: string;
    wsAudioDownloadUrl?: string;
    maxHistory?: number | number[];
    controlLayout?: Record<string, { x: number; y: number }> | string;
  }) {
    if (typeof data.serverUrl === 'string') {
      this.database.setSetting('ui.serverUrl', data.serverUrl);
    }
    if (typeof data.wsPath === 'string') {
      this.database.setSetting('ui.wsPath', data.wsPath);
    }
    if (typeof data.wsControlUrl === 'string') {
      this.database.setSetting('ui.wsControlUrl', data.wsControlUrl);
    }
    if (typeof data.wsBusinessUrl === 'string') {
      this.database.setSetting('ui.wsBusinessUrl', data.wsBusinessUrl);
    }
    if (typeof data.wsAudioUploadUrl === 'string') {
      this.database.setSetting('ui.wsAudioUploadUrl', data.wsAudioUploadUrl);
    }
    if (typeof data.wsAudioDownloadUrl === 'string') {
      this.database.setSetting('ui.wsAudioDownloadUrl', data.wsAudioDownloadUrl);
    }
    if (typeof data.maxHistory !== 'undefined') {
      const mh = Array.isArray(data.maxHistory) ? Number(data.maxHistory[0]) : Number(data.maxHistory);
      if (!Number.isNaN(mh)) {
        this.database.setSetting('ui.maxHistory', String(mh));
      }
    }
    if (typeof data.controlLayout !== 'undefined') {
      const layoutValue = typeof data.controlLayout === 'string'
        ? data.controlLayout
        : JSON.stringify(data.controlLayout || {});
      this.database.setSetting('ui.controlLayout', layoutValue);
    }
  }

  checkUpdate(robotId?: string) {
    const robot = robotId ? this.database.getRobot(robotId) : undefined;
    return {
      checkedAt: new Date().toISOString(),
      app: { currentVersion: '', latestVersion: '', hasUpdate: false },
      firmware: { currentVersion: robot?.version || '', latestVersion: robot?.version || '', hasUpdate: false },
    };
  }
}
