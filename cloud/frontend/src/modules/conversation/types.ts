// 对话模块 - 类型定义

export interface Message {
  id: string
  robotId: string
  timestamp: string
  type: 'user' | 'assistant' | 'system'
  content: string
  actions?: Action[]
  metadata?: MessageMetadata
}

export interface Action {
  name: string
  parameters?: Record<string, any>
  status?: 'pending' | 'executing' | 'success' | 'failed'
}

export interface MessageMetadata {
  model?: string
  tokensUsed?: number
  responseTime?: number
  from?: string
}

export interface Conversation {
  uuid: number
  robot_id: string
  timestamp: string
  type: 'audio' | 'text'
  user_input: string
  ai_response: string
  actions?: string
  processing_time?: number
  metadata?: string
}

export interface ConversationHistoryResponse {
  success: boolean
  data: {
    conversations: Conversation[]
    limit: number
    offset: number
  }
}

export interface SendCommandDTO {
  text: string
}

export interface ApiResponse {
  success: boolean
  message?: string
  data?: any
}
