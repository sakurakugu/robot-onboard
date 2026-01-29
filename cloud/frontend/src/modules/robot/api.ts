// 机器人模块 - API

import { http } from '@/api/request'
import type {
    ApiResponse,
    ConnectionTestResult,
    CreateRobotDTO,
    RobotGroupsResponse,
    RobotListResponse,
    RobotResponse,
    UpdateRobotDTO
} from './types'

/**
 * 获取所有机器人列表
 */
export function getRobotList() {
  return http.get<RobotListResponse>('/api/v1/robots')
}

/**
 * 获取机器人分组
 */
export function getRobotGroups() {
  return http.get<RobotGroupsResponse>('/api/v1/robots/groups')
}

/**
 * 获取指定机器人信息
 */
export function getRobotDetail(uuid: string) {
  return http.get<RobotResponse>(`/api/v1/robots/${uuid}`)
}

/**
 * 创建机器人
 */
export function createRobot(data: CreateRobotDTO) {
  return http.post<RobotResponse>('/api/v1/robots', data)
}

/**
 * 更新机器人信息
 */
export function updateRobot(uuid: string, data: UpdateRobotDTO) {
  return http.put<RobotResponse>(`/api/v1/robots/${uuid}`, data)
}

/**
 * 删除机器人
 */
export function deleteRobot(uuid: string) {
  return http.delete<ApiResponse>(`/api/v1/robots/${uuid}`)
}

/**
 * 测试机器人连接
 */
export function testRobotConnection(uuid: string) {
  return http.post<ConnectionTestResult>(`/api/v1/robots/${uuid}/test-connection`)
}

/**
 * 连接机器人
 */
export function connectRobot(uuid: string) {
  return http.post<RobotResponse>(`/api/v1/robots/${uuid}/connect`)
}

/**
 * 更新机器人固件
 */
export function updateRobotFirmware(uuid: string) {
  return http.post<ApiResponse>(`/api/v1/robots/${uuid}/update-firmware`)
}

/**
 * 获取日志上传历史
 */
export function getLogHistory(uuid: string, limit = 5) {
  return http.get<ApiResponse>(`/api/v1/robots/${uuid}/logs/history`, {
    params: { limit },
  })
}

/**
 * 上传日志
 */
export function uploadLog(uuid: string, data: { from?: string; to?: string; logType?: string }) {
  return http.post<ApiResponse>(`/api/v1/robots/${uuid}/logs/upload`, data)
}
