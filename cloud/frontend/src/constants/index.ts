// 应用常量定义

// API 基础地址
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:9004'
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:9001'
export const WS_CONTROL_BASE_URL = import.meta.env.VITE_WS_CONTROL_BASE_URL || 'ws://localhost:9000'
export const WS_BIZ_BASE_URL = import.meta.env.VITE_WS_BIZ_BASE_URL || 'ws://localhost:9001'
export const WS_AUDIO_UPLOAD_BASE_URL = import.meta.env.VITE_WS_AUDIO_UPLOAD_BASE_URL || 'ws://localhost:9002'
export const WS_AUDIO_DOWNLOAD_BASE_URL = import.meta.env.VITE_WS_AUDIO_DOWNLOAD_BASE_URL || 'ws://localhost:9003'

// WebSocket 路径
export const WS_PATH = '/api/v1/conversation/connect' // WebSocket 连接路径

// 机器人状态
export const ROBOT_STATUS = {
  ONLINE: 'online',  // 在线
  OFFLINE: 'offline',// 离线
  ERROR: 'error',    // 错误
} as const

export const ROBOT_STATUS_LABELS = {
  online: '在线',
  offline: '离线',
  error: '错误',
}

export const ROBOT_STATUS_COLORS = {
  online: 'success', // 成功（绿色）
  offline: 'info',   // 信息（蓝色）
  error: 'danger',   // 危险（红色）
} as const

// LLM 提供商
export const LLM_PROVIDERS = {
  OPENAI: 'openai',      // OpenAI 提供商
  BIGMODEL: 'bigmodel',  // 大模型提供商
  ANTHROPIC: 'anthropic',// Anthropic 提供商
  DEEPSEEK: 'deepseek',  // DeepSeek 提供商
} as const

// 消息类型
export const MESSAGE_TYPE = {
  USER: 'user',           // 用户消息
  ASSISTANT: 'assistant', // 助手消息
  SYSTEM: 'system',       // 系统消息
} as const

// 对话类型
export const CONVERSATION_TYPE = {
  TEXT: 'text',        // 文本对话
  AUDIO: 'audio',      // 音频对话
} as const

// 日志类型
export const LOG_TYPE = {
  ROBOT: 'robot',   // 机器人日志
  SERVER: 'server', // 服务器日志
  APP: 'app',       // 应用日志
  ALL: 'all',       // 所有日志
} as const

// 分页默认值
export const DEFAULT_PAGE_SIZE = 20 // 默认每页数量
export const DEFAULT_PAGE = 1       // 默认当前页

// 请求超时时间
export const REQUEST_TIMEOUT = 30000  // 默认请求超时时间（毫秒）

// WebSocket 配置
export const WS_CONFIG = {
  HEARTBEAT_INTERVAL: 30000,  // 心跳间隔（毫秒）
  RECONNECT_INTERVAL: 3000,   // 重连间隔（毫秒）
  MAX_RECONNECT_ATTEMPTS: 5,   // 最大重连尝试次数
}

// 路由路径
export const ROUTES = {
  HOME: '/',               // 首页
  ROBOTS: '/robots',       // 机器人列表
  ROBOT_DETAIL: '/robots/:uuid',            // 机器人详情
  ROBOT_SETTINGS: '/robots/:uuid/settings', // 机器人设置
  CHAT: '/chat/:uuid',     // 聊天界面
  OPERATION: '/operation', // 操作界面 (改成/operation/:uuid)
  PARAMS: '/params',       // 参数界面（指ws路径，后端路径，api等等）
  KNOWLEDGE_BASE: '/kb',   // 知识库  （到时候也要加uuid，这是指比如有分类垃圾的知识库，移动展厅的知识库等等）
  SETTINGS: '/settings',   // 设置界面（配置，如深色模式等）
} as const

// 存储键名（TODO:这里是储存在本地的用户数据，到时候可以考虑把显示语言设置等等存放到用户数据库中）
export const STORAGE_KEYS = {
  TOKEN: 'token',               // 认证令牌
  USER_INFO: 'userInfo',        // 用户信息
  THEME: 'theme',               // 主题设置
  LANGUAGE: 'language',         // 语言设置
  LAST_ROBOT_ID: 'lastRobotId', // 最后选择的机器人ID
} as const
