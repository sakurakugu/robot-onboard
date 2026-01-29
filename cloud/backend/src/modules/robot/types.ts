// 机器人相关类型定义

// 数据库相关
export interface RobotRecord {
  uuid: string;
  name?: string;
  model?: string;
  version?: string;
  ip?: string;
  group_name?: string | null;
  tags?: string | null; // JSON string (array)
  sn?: string | null;
  role_id?: string | null;
  status: 'online' | 'offline' | 'error';
  last_connected?: Date;
  registered_at?: Date | null;
  updated_at?: Date;
  created_at: Date;
  metadata?: string; // JSON string
}
