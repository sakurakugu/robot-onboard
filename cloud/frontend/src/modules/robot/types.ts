// 机器人模块 - 类型定义

export interface Robot {
  uuid: string
  name?: string
  model?: string
  version?: string
  ip?: string
  robot_ip?: string
  group_name?: string | null
  tags?: string[]
  sn?: string | null
  status: 'online' | 'offline' | 'error'
  last_connected?: string
  registered_at?: string
  created_at?: string
  updated_at?: string
  metadata?: Record<string, any>
  
  // AI配置
  ai_temperature?: number
  ai_system_prompt?: string
  ai_voice?: string
  ai_intent?: string
  ai_role_name?: string
  
  // 状态信息
  lastStatus?: string
  lastStatusTime?: string
}

export interface CreateRobotDTO {
  name?: string
  ip?: string
  robot_ip?: string
  group_name?: string
  model?: string
  status?: string
  sn?: string
  tags?: string[] | string
}

export interface UpdateRobotDTO {
  name?: string
  model?: string
  ip?: string
  status?: string
  group_name?: string
  sn?: string
  tags?: string[] | string
  ai_temperature?: number
  ai_system_prompt?: string
  ai_voice?: string
  ai_intent?: string
  ai_role_name?: string
}

export interface RobotListResponse {
  success: boolean
  data: {
    robots: Robot[]
    onlineCount?: number
  }
}

export interface RobotResponse {
  success: boolean
  data: Robot
}

export interface RobotGroupsResponse {
  success: boolean
  data: {
    groups: string[]
  }
}

export interface ConnectionTestResult {
  success: boolean
  connected: boolean
  message: string
}

export interface LogUploadRecord {
  id: string
  time: string
  logType: 'robot' | 'app' | 'all'
  size: number
  range: {
    from: string | null
    to: string | null
  }
}

export interface ApiResponse {
  success: boolean
  message?: string
  data?: any
}
