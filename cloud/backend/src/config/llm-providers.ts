// 导出大模型供应商值类型
export type LLMProviderValue = 'openai' | 'anthropic' | 'deepseek' | 'bigmodel' | 'tongyi'

// 导出大模型模型接口
export interface LLMModel {
  value: string
  label: string
}

// 导出大模型供应商配置接口
export interface LLMProviderConfig {
  value: LLMProviderValue
  label: string
  baseUrl?: string
  models: LLMModel[]
}

// 导出大模型供应商配置数组
export const LLM_PROVIDERS: LLMProviderConfig[] = [
  {
    value: 'openai',
    label: 'OpenAI（开放AI）',
    baseUrl: 'https://api.openai.com/v1',
    models: [
      { value: 'gpt-5-nano', label: 'GPT-5 Nano' },
      { value: 'gpt-5-mini', label: 'GPT-5 Mini' },
      { value: 'gpt-5.2', label: 'GPT-5.2' }
    ]
  },
  {
    value: 'bigmodel',
    label: '智谱 （BigModel）',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    models: [
      { value: 'glm-4.7-flash', label: 'GLM 4.7 Flash' },
      { value: 'glm-4.7-flashx', label: 'GLM 4.7' },
    ]
  },
  {
    value: 'anthropic',
    label: 'Claude（Anthropic）',
    baseUrl: 'https://api.anthropic.com/v1/messages',
    models: [
      { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
      { value: 'claude-opus-4-5', label: 'Claude Opus 4.5' },
      { value: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' }
    ]
  },
  {
    value: 'deepseek',
    label: 'DeepSeek（深度求索）',
    baseUrl: 'https://api.deepseek.com',
    models: [
      { value: 'deepseek-reasoner', label: 'DeepSeek v3.2(深度思考)' },
      { value: 'deepseek-chat', label: 'DeepSeek v3.2' }
    ]
  },
  {
    value: 'tongyi',
    label: '通义千问',
    baseUrl: 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
    models: [
      { value: 'qwen3-0.5b-instruct', label: 'Qwen 3 0.5B' },
      { value: 'qwen3-1.5b-instruct', label: 'Qwen 3 1.5B' },
      { value: 'qwen3-3b-instruct', label: 'Qwen 3 3B' },
      { value: 'qwen3-7b-instruct', label: 'Qwen 3 7B' },
      { value: 'qwen3-14b-instruct', label: 'Qwen 3 14B' },
      { value: 'qwen3-32b-instruct', label: 'Qwen 3 32B' },
      { value: 'qwen3-72b-instruct', label: 'Qwen 3 72B' },
      { value: 'qwen3-flash', label: 'Qwen 3 Flash' },
      { value: 'qwen3-flash-1.5b', label: 'Qwen 3 Flash 1.5B' },
      { value: 'qwen3-flash-7b', label: 'Qwen 3 Flash 7B' },
      { value: 'qwen3-flash-14b', label: 'Qwen 3 Flash 14B' }
    ]
  }
]
