// 角色相关类型定义

export interface RoleRecord {
  uuid: string;
  name: string;
  description?: string;
  llm_provider?: string;
  llm_model?: string;
  temperature?: number;
  system_prompt?: string;
  voice?: string;
  intent_strategy?: string;
   max_history?: number;
  created_at: string;
  updated_at: string;
}

export interface CreateRoleDto {
  name: string;
  description?: string;
  llm_provider?: string;
  llm_model?: string;
  temperature?: number;
  system_prompt?: string;
  voice?: string;
  intent_strategy?: string;
  max_history?: number;
}

export interface UpdateRoleDto {
  name?: string;
  description?: string;
  llm_provider?: string;
  llm_model?: string;
  temperature?: number;
  system_prompt?: string;
  voice?: string;
  intent_strategy?: string;
  max_history?: number;
}
