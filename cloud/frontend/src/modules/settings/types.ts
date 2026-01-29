// 系统设置模块 - 类型定义

export interface LLMConfig {
  provider: 'openai' | 'bigmodel' | 'anthropic' | 'deepseek'
  openai: {
    model: string
    baseUrl: string
    hasApiKey: boolean
    apiKeyLength: number
  }
  bigmodel: {
    model: string
    baseUrl: string
    hasApiKey: boolean
    apiKeyLength: number
  }
}

export interface UpdateLLMConfigDTO {
  provider?: string
  apiKey?: string
  model?: string
  baseUrl?: string
}

export interface LLMProvider {
  id: string
  name: string
  models: LLMModel[]
}

export interface LLMModel {
  id: string
  name: string
  description?: string
}

export interface UIConfig {
  serverUrl: string
  wsPath: string
  wsControlUrl?: string
  wsBusinessUrl?: string
  wsAudioUploadUrl?: string
  wsAudioDownloadUrl?: string
  maxHistory: number
  controlLayout?: Record<string, { x: number; y: number }> | null
}

export interface UpdateUIConfigDTO {
  serverUrl?: string
  wsPath?: string
  wsControlUrl?: string
  wsBusinessUrl?: string
  wsAudioUploadUrl?: string
  wsAudioDownloadUrl?: string
  maxHistory?: number
  controlLayout?: Record<string, { x: number; y: number }>
}

export interface SystemStatus {
  onlineRobots: number
  totalRobots: number
  timestamp: string
}

export interface NetworkInfo {
  ip: string
  all: string[]
}

export interface UpdateInfo {
  checkedAt: string
  app: {
    currentVersion: string
    latestVersion: string
    hasUpdate: boolean
  }
  firmware: {
    currentVersion: string
    latestVersion: string
    hasUpdate: boolean
  }
}

export interface ApiResponse<T = any> {
  success: boolean
  message?: string
  data?: T
}
