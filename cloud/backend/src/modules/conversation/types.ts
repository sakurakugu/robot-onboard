// 对话和动作相关类型定义

// 动作相关
export interface Action {
  name: string;
  parameters: Record<string, any>;
  priority?: number;
}

export interface ActionCommand {
  action: string;
  parameters: Record<string, any>;
  safetyChecked: boolean;
}

export interface SafetyCheckResult {
  safe: boolean;
  reason?: string;
  sanitizedAction?: Action;
}

export interface SafetyRule {
  action: string;
  maxValue?: number;
  minValue?: number;
  maxFrequency?: number;
}

// AI相关
export interface ConversationContext {
  history: Message[];
  maxHistory: number;
  systemPrompt?: string;
  model?: string;
  temperature?: number;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export interface AIResponse {
  text: string;
  actions: Action[];
  emotions?: string[];
  metadata: {
    model: string;
    tokensUsed: number;
    responseTime: number;
  };
}

// 语音服务
export interface RecognitionResult {
  text: string;
  confidence: number;
  segments?: {
    text: string;
    startTime: number;
    endTime: number;
  }[];
}

export interface TTSOptions {
  voice?: string;
  speed?: number;
  pitch?: number;
  volume?: number;
}

// LLM相关
export interface LLMOptions {
  model: string;
  temperature?: number;
  maxTokens?: number;
  tools?: Tool[];
}

export interface Tool {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: any;
  };
}

export interface LLMResponse {
  content: string;
  finishReason: string;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  toolCalls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

// 知识库
export interface Document {
  uuid: string;
  content: string;
  metadata: {
    title?: string;
    source?: string;
    category?: string;
    tags?: string[];
    createdAt: Date;
  };
  embedding?: number[];
}

// 日志
export interface ConversationLog {
  id: string;
  robotId: string;
  timestamp: Date;
  type: 'audio' | 'text';
  input: {
    raw?: Buffer;
    text: string;
    duration?: number;
  };
  processing: {
    asrTime?: number;
    llmTime: number;
    ttsTime?: number;
    totalTime: number;
  };
  output: {
    text: string;
    actions: Action[];
    audio?: Buffer;
  };
  metadata: {
    model: string;
    tokensUsed: number;
    cost?: number;
  };
}

// 数据库相关
export interface ConversationRecord {
  uuid: number;
  robot_id: string;
  timestamp: Date;
  type: 'audio' | 'text';
  user_input: string;
  ai_response: string;
  actions?: string; // JSON string
  processing_time: number;
  metadata?: string; // JSON string
}

export interface ActionLogRecord {
  uuid: number;
  robot_id: string;
  action_name: string;
  parameters?: string; // JSON string
  status: 'success' | 'failed' | 'rejected';
  executed_at: Date;
}
