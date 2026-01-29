// WebSocket 模块 - 类型定义

export type WebSocketRole = 'robot' | 'ui'

export interface WebSocketMessage {
  type: string
  robotId?: string
  timestamp: number
  data?: any
}

export interface ServerMessage extends WebSocketMessage {
  type: 'text_response' | 'audio_response' | 'action_command' | 'status_update' | 'error'
}

export interface ClientMessage extends WebSocketMessage {
  type: 'text_message' | 'audio_message' | 'status_report' | 'heartbeat'
}

export interface WebSocketConnectionOptions {
  robotId: string
  role: WebSocketRole
  autoReconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting'
