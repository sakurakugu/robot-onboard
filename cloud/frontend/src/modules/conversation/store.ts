// 对话模块 - 状态管理

import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as conversationApi from './api'
import type { Conversation, Message } from './types'

export const useConversationStore = defineStore('conversation', () => {
  // 状态
  const conversations = ref<Conversation[]>([])
  const messages = ref<Message[]>([])
  const currentRobotId = ref<string>('')
  const loading = ref(false)
  
  // 计算属性
  const conversationCount = computed(() => conversations.value.length)
  
  const messagesByRobot = computed(() => {
    if (!currentRobotId.value) return []
    return messages.value.filter(m => m.robotId === currentRobotId.value)
  })

  // 方法
  async function fetchConversationHistory(robotId: string, limit = 50, offset = 0) {
    loading.value = true
    try {
      const res = await conversationApi.getConversationHistory(robotId, limit, offset)
      conversations.value = res.data.conversations
      currentRobotId.value = robotId
      return res.data
    } catch (error) {
      console.error('获取对话历史失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function sendCommand(robotId: string, text: string) {
    try {
      await conversationApi.sendCommand(robotId, { text })
      ElMessage.success('命令发送成功')
    } catch (error) {
      console.error('发送命令失败:', error)
      throw error
    }
  }

  function addMessage(message: Message) {
    messages.value.push(message)
  }

  function clearMessages() {
    messages.value = []
  }

  function setCurrentRobotId(robotId: string) {
    currentRobotId.value = robotId
  }

  return {
    // 状态
    conversations,
    messages,
    currentRobotId,
    loading,
    
    // 计算属性
    conversationCount,
    messagesByRobot,
    
    // 方法
    fetchConversationHistory,
    sendCommand,
    addMessage,
    clearMessages,
    setCurrentRobotId,
  }
})
