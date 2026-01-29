import dotenv from 'dotenv';
import path from 'path';

dotenv.config();

export interface Config {
  // 服务配置
  port: number;
  ports: {
    http: number;
    control: number;
    business: number;
    audioUpload: number;
    audioDownload: number;
  };
  nodeEnv: string;

  // WebSocket配置
  ws: {
    path: string;
    maxConnections: number;
  };

  // AI服务配置
  llm: {
    provider: 'openai' | 'anthropic' | 'tongyi' | 'deepseek' | 'bigmodel';
    openai?: {
      apiKey: string;
      model: string;
      baseUrl?: string;
    };
    bigmodel?: {
      apiKey: string;
      model: string;
      baseUrl?: string;
    };
  };

  // 语音识别配置
  asr: {
    provider: 'xunfei' | 'aliyun' | 'azure' | 'openai';
    xunfei?: {
      appId: string;
      apiKey: string;
      apiSecret: string;
    };
    openai?: {
      apiKey: string;
      model: string;
      baseUrl?: string;
      language?: string;
      prompt?: string;
    };
  };

  // 语音合成配置
  tts: {
    provider: 'xunfei' | 'aliyun' | 'azure';
    xunfei?: {
      appId: string;
      apiKey: string;
      apiSecret: string;
    };
  };

  // 数据库配置
  database: {
    type: 'sqlite';
    path?: string;
  };

  // 日志配置
  logging: {
    level: string;
    dir: string;
  };

  // 安全配置
  security: {
    jwtSecret: string;
    rateLimit: {
      max: number;
      windowMs: number;
    };
  };
}

const config: Config = {
  port: parseInt(process.env.PORT || '9004', 10),
  ports: {
    http: parseInt(process.env.PORT || '9004', 10),
    control: parseInt(process.env.CONTROL_PORT || '9000', 10),
    business: parseInt(process.env.BUSINESS_PORT || '9001', 10),
    audioUpload: parseInt(process.env.AUDIO_UPLOAD_PORT || '9002', 10),
    audioDownload: parseInt(process.env.AUDIO_DOWNLOAD_PORT || '9003', 10),
  },
  nodeEnv: process.env.NODE_ENV || 'development',

  ws: {
    path: process.env.WS_PATH || '/api/v1/conversation/connect',
    maxConnections: parseInt(process.env.WS_MAX_CONNECTIONS || '100', 10),
  },

  llm: {
    // 仅从数据库加载配置，不使用 .env
    // 以下为初始默认值，会被数据库配置完全覆盖
    provider: 'bigmodel',
    openai: {
      apiKey: '',
      model: 'gpt-4',
      baseUrl: 'https://api.openai.com/v1',
    },
    bigmodel: {
      apiKey: '',
      model: 'glm-4-flash',
      baseUrl: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    },
  },

  asr: {
    provider: (process.env.ASR_PROVIDER as any) || 'xunfei',
    xunfei: {
      appId: process.env.XUNFEI_ASR_APP_ID || '',
      apiKey: process.env.XUNFEI_ASR_API_KEY || '',
      apiSecret: process.env.XUNFEI_ASR_API_SECRET || '',
    },
    openai: {
      apiKey: process.env.OPENAI_ASR_API_KEY || '',
      model: process.env.OPENAI_ASR_MODEL || 'whisper-1',
      baseUrl: process.env.OPENAI_ASR_BASE_URL || 'https://api.openai.com/v1',
      language: process.env.OPENAI_ASR_LANGUAGE || 'zh',
      prompt: process.env.OPENAI_ASR_PROMPT || '',
    },
  },

  tts: {
    provider: (process.env.TTS_PROVIDER as any) || 'xunfei',
    xunfei: {
      appId: process.env.XUNFEI_TTS_APP_ID || '',
      apiKey: process.env.XUNFEI_TTS_API_KEY || '',
      apiSecret: process.env.XUNFEI_TTS_API_SECRET || '',
    },
  },

  database: {
    type: (process.env.DB_TYPE as any) || 'sqlite',
    path: process.env.DB_PATH || path.join(__dirname, '../../data/conversations.db'),
  },

  logging: {
    level: process.env.LOG_LEVEL || 'info',
    dir: process.env.LOG_DIR || path.join(__dirname, '../../data/logs'),
  },

  security: {
    jwtSecret: process.env.JWT_SECRET || 'your-secret-key',
    rateLimit: {
      max: parseInt(process.env.RATE_LIMIT_MAX || '100', 10),
      windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10),
    },
  },
};

export default config;
