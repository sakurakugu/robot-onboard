// 系统设置模块 - 状态管理

import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as settingsApi from './api'
import type { LLMConfig, LLMProvider, SystemStatus, UIConfig } from './types'

export const useSettingsStore = defineStore('settings', () => {
  // 状态
  const llmConfig = ref<LLMConfig | null>(null)
  const llmProviders = ref<LLMProvider[]>([])
  const uiConfig = ref<UIConfig | null>(null)
  const systemStatus = ref<SystemStatus | null>(null)
  const loading = ref(false)

  // 方法
  async function fetchLLMConfig() {
    loading.value = true
    try {
      const res = await settingsApi.getLLMConfig()
      llmConfig.value = res.data ?? null
      return res.data
    } catch (error) {
      console.error('获取LLM配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchLLMProviders() {
    try {
      const res = await settingsApi.getLLMProviders()
      llmProviders.value = res.data ?? []
      return res.data
    } catch (error) {
      console.error('获取LLM提供商列表失败:', error)
      throw error
    }
  }

  async function updateLLMConfig(data: any) {
    loading.value = true
    try {
      await settingsApi.updateLLMConfig(data)
      await fetchLLMConfig() // 重新获取配置
      ElMessage.success('配置更新成功')
    } catch (error) {
      console.error('更新LLM配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchUIConfig() {
    loading.value = true
    try {
      const res = await settingsApi.getUIConfig()
      uiConfig.value = res.data ?? null
      return res.data
    } catch (error) {
      console.error('获取UI配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateUIConfig(data: any) {
    loading.value = true
    try {
      await settingsApi.updateUIConfig(data)
      await fetchUIConfig() // 重新获取配置
      ElMessage.success('配置更新成功')
    } catch (error) {
      console.error('更新UI配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchSystemStatus() {
    try {
      const res = await settingsApi.getSystemStatus()
      systemStatus.value = res.data ?? null
      return res.data
    } catch (error) {
      console.error('获取系统状态失败:', error)
      throw error
    }
  }

  async function getLocalIP() {
    try {
      const res = await settingsApi.getLocalIP()
      return res.data
    } catch (error) {
      console.error('获取本机IP失败:', error)
      throw error
    }
  }

  async function checkUpdate(robotId?: string) {
    try {
      const res = await settingsApi.checkUpdate(robotId)
      return res.data
    } catch (error) {
      console.error('检查更新失败:', error)
      throw error
    }
  }

  return {
    // 状态
    llmConfig,
    llmProviders,
    uiConfig,
    systemStatus,
    loading,
    
    // 方法
    fetchLLMConfig,
    fetchLLMProviders,
    updateLLMConfig,
    fetchUIConfig,
    updateUIConfig,
    fetchSystemStatus,
    getLocalIP,
    checkUpdate,
  }
})
