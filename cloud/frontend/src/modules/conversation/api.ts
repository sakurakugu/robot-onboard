// 对话模块 - API

import { http } from '@/api/request'
import type { ApiResponse, ConversationHistoryResponse, SendCommandDTO } from './types'

/**
 * 获取对话历史
 */
export function getConversationHistory(robotId: string, limit = 50, offset = 0) {
  return http.get<ConversationHistoryResponse>(`/api/v1/conversations/${robotId}`, {
    params: { limit, offset },
  })
}

/**
 * 发送文本命令到机器人
 */
export function sendCommand(robotId: string, data: SendCommandDTO) {
  return http.post<ApiResponse>(`/api/v1/robot/${robotId}/command`, data)
}
