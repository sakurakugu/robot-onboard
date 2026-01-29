// 系统设置模块 - API

import { http } from '@/api/request'
import type {
    ApiResponse,
    LLMConfig,
    LLMProvider,
    NetworkInfo,
    SystemStatus,
    UIConfig,
    UpdateInfo,
    UpdateLLMConfigDTO,
    UpdateUIConfigDTO,
} from './types'

/**
 * 获取 LLM 配置
 */
export function getLLMConfig() {
  return http.get<ApiResponse<LLMConfig>>('/api/v1/config/llm')
}

/**
 * 获取 LLM 提供商列表
 */
export function getLLMProviders() {
  return http.get<ApiResponse<LLMProvider[]>>('/api/v1/config/llm/providers')
}

/**
 * 更新 LLM 配置
 */
export function updateLLMConfig(data: UpdateLLMConfigDTO) {
  return http.put<ApiResponse>('/api/v1/config/llm', data)
}

/**
 * 获取 UI 配置
 */
export function getUIConfig() {
  return http.get<ApiResponse<UIConfig>>('/api/v1/config/ui')
}

/**
 * 更新 UI 配置
 */
export function updateUIConfig(data: UpdateUIConfigDTO) {
  return http.put<ApiResponse>('/api/v1/config/ui', data)
}

/**
 * 获取系统状态
 */
export function getSystemStatus() {
  return http.get<ApiResponse<SystemStatus>>('/api/v1/status')
}

/**
 * 健康检查
 */
export function healthCheck() {
  return http.get<ApiResponse>('/api/v1/health')
}

/**
 * 获取本机 IP
 */
export function getLocalIP() {
  return http.get<ApiResponse<NetworkInfo>>('/api/v1/network/local-ip')
}

/**
 * 检查更新
 */
export function checkUpdate(robotId?: string) {
  return http.get<ApiResponse<UpdateInfo>>('/api/v1/updates/check', {
    params: robotId ? { robotId } : undefined,
  })
}

/**
 * 升级应用
 */
export function upgradeApp() {
  return http.post<ApiResponse>('/api/v1/updates/upgrade/app')
}
