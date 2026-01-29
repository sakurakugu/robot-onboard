// WebSocket 模块 - 状态管理

import { WS_BASE_URL, WS_CONFIG, WS_PATH } from '@/constants'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { WebSocketMessage, WebSocketStatus } from './types'

export const useWebSocketStore = defineStore('websocket', () => {
  // 状态
  const ws = ref<WebSocket | null>(null)
  const status = ref<WebSocketStatus>('disconnected')
  const robotId = ref<string>('')
  const role = ref<'robot' | 'ui'>('ui')
  const reconnectAttempts = ref(0)
  const reconnectTimer = ref<number | null>(null)

  // 计算属性
  const isConnected = computed(() => status.value === 'connected')
  const isConnecting = computed(() => status.value === 'connecting')
  const canReconnect = computed(() => 
    reconnectAttempts.value < WS_CONFIG.MAX_RECONNECT_ATTEMPTS
  )

  // 消息回调
  const messageHandlers = ref<Map<string, Set<(data: any) => void>>>(new Map())

  // 方法
  function connect(rid: string, wsRole: 'robot' | 'ui' = 'ui') {
    if (ws.value) {
      disconnect()
    }

    robotId.value = rid
    role.value = wsRole
    status.value = 'connecting'

    const url = `${WS_BASE_URL}${WS_PATH}?robotId=${rid}&role=${wsRole}`
    
    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        status.value = 'connected'
        reconnectAttempts.value = 0
        console.log('WebSocket connected:', url)
      }

      ws.value.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.value.onerror = (error) => {
        console.error('WebSocket error:', error)
        status.value = 'error'
      }

      ws.value.onclose = () => {
        console.log('WebSocket disconnected')
        status.value = 'disconnected'
        ws.value = null
        
        // 自动重连
        if (canReconnect.value) {
          attemptReconnect()
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      status.value = 'error'
    }
  }

  function disconnect() {
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }

    status.value = 'disconnected'
    reconnectAttempts.value = 0
  }

  function send(message: any) {
    if (!ws.value || status.value !== 'connected') {
      console.error('WebSocket is not connected')
      return false
    }

    try {
      ws.value.send(JSON.stringify(message))
      return true
    } catch (error) {
      console.error('Failed to send WebSocket message:', error)
      return false
    }
  }

  function attemptReconnect() {
    if (!canReconnect.value || reconnectTimer.value) {
      return
    }

    status.value = 'reconnecting'
    reconnectAttempts.value++

    reconnectTimer.value = window.setTimeout(() => {
      reconnectTimer.value = null
      connect(robotId.value, role.value)
    }, WS_CONFIG.RECONNECT_INTERVAL)
  }

  function handleMessage(message: WebSocketMessage) {
    const handlers = messageHandlers.value.get(message.type)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message.data)
        } catch (error) {
          console.error(`Error in message handler for ${message.type}:`, error)
        }
      })
    }

    // 全局消息处理器
    const globalHandlers = messageHandlers.value.get('*')
    if (globalHandlers) {
      globalHandlers.forEach(handler => {
        try {
          handler(message)
        } catch (error) {
          console.error('Error in global message handler:', error)
        }
      })
    }
  }

  function on(messageType: string, handler: (data: any) => void) {
    if (!messageHandlers.value.has(messageType)) {
      messageHandlers.value.set(messageType, new Set())
    }
    messageHandlers.value.get(messageType)!.add(handler)
  }

  function off(messageType: string, handler?: (data: any) => void) {
    if (!handler) {
      messageHandlers.value.delete(messageType)
    } else {
      const handlers = messageHandlers.value.get(messageType)
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  return {
    // 状态
    ws,
    status,
    robotId,
    role,
    reconnectAttempts,
    
    // 计算属性
    isConnected,
    isConnecting,
    canReconnect,
    
    // 方法
    connect,
    disconnect,
    send,
    on,
    off,
  }
})
