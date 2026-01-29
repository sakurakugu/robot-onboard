import Database from 'better-sqlite3';
import path from 'path';
import config from '../../config';
import { ConversationRecord, RobotRecord } from '../../types';

class DatabaseService {
  private db!: Database.Database;

  constructor() {
    this.init();
  }

  private init() {
    const dbPath = config.database.path!;
    const dbDir = path.dirname(dbPath);

    // 确保数据目录存在
    if (!require('fs').existsSync(dbDir)) {
      require('fs').mkdirSync(dbDir, { recursive: true });
    }

    this.db = new Database(dbPath);
    this.initTables();
    
    // 执行数据库列迁移
    this.migrateColumns();
    
    // 执行数据迁移
    this.migrateIPFromMetadata();
  }

  private migrateColumns(): void {
    try {
      // 检查roles表是否存在并添加缺失列
      const rolesTableExists = this.db.prepare(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='roles'"
      ).get();
      if (rolesTableExists) {
        const roleCols = this.db.prepare(`PRAGMA table_info(roles)`).all() as any[];
        const hasMaxHistory = roleCols.some((c: any) => c.name === 'max_history');
        if (!hasMaxHistory) {
          try {
            this.db.exec(`ALTER TABLE roles ADD COLUMN max_history INTEGER DEFAULT 10`);
          } catch (e) {}
        }
      }

      // 检查robots表是否存在
      const tableExists = this.db.prepare(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='robots'"
      ).get();
      
      if (!tableExists) {
        console.log('robots表尚未创建，跳过列迁移');
        return;
      }

      // 检查robots表列
      const cols = this.db.prepare(`PRAGMA table_info(robots)`).all() as any[];
      const hasIP = cols.some((c: any) => c.name === 'ip');
      const hasGroupName = cols.some((c: any) => c.name === 'group_name');
      const hasTags = cols.some((c: any) => c.name === 'tags');
      const hasSn = cols.some((c: any) => c.name === 'sn');
      const hasRegisteredAt = cols.some((c: any) => c.name === 'registered_at');
      const hasUpdatedAt = cols.some((c: any) => c.name === 'updated_at');
      const hasRoleId = cols.some((c: any) => c.name === 'role_id');
      
      if (!hasIP) {
        console.log('添加ip列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN ip TEXT`);
          console.log('ip列添加成功');
        } catch (e) {
          console.error('ip列添加失败:', e);
        }
      }
      if (!hasGroupName) {
        console.log('添加group_name列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN group_name TEXT`);
          console.log('group_name列添加成功');
        } catch (e) {
          console.error('group_name列添加失败:', e);
        }
      }
      if (!hasTags) {
        console.log('添加tags列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN tags TEXT`);
          console.log('tags列添加成功');
        } catch (e) {
          console.error('tags列添加失败:', e);
        }
      }
      if (!hasSn) {
        console.log('添加sn列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN sn TEXT`);
          console.log('sn列添加成功');
        } catch (e) {
          console.error('sn列添加失败:', e);
        }
      }
      if (!hasRegisteredAt) {
        console.log('添加registered_at列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN registered_at DATETIME`);
          console.log('registered_at列添加成功');
        } catch (e) {
          console.error('registered_at列添加失败:', e);
        }
      }
      if (!hasUpdatedAt) {
        console.log('添加updated_at列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP`);
          console.log('updated_at列添加成功');
        } catch (e) {
          console.error('updated_at列添加失败:', e);
        }
      }
      if (!hasRoleId) {
        console.log('添加role_id列到robots表...');
        try {
          this.db.exec(`ALTER TABLE robots ADD COLUMN role_id TEXT`);
          console.log('role_id列添加成功');
        } catch (e) {
          console.error('role_id列添加失败:', e);
        }
      }
    } catch (error) {
      console.error('列迁移失败:', error);
    }
  }

  private initTables(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS params (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    // 系统设置表（用于持久化运行时配置）
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 角色表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS roles (
        uuid TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        llm_provider TEXT,
        llm_model TEXT,
        temperature REAL DEFAULT 0.7,
        system_prompt TEXT,
        voice TEXT,
        intent_strategy TEXT,
        max_history INTEGER DEFAULT 10,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 机器狗注册表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS robots (
        uuid TEXT PRIMARY KEY,
        name TEXT,
        model TEXT,
        version TEXT,
        ip TEXT,
        group_name TEXT,
        tags TEXT,
        sn TEXT,
        role_id TEXT,
        status TEXT DEFAULT 'offline',
        last_connected DATETIME,
        registered_at DATETIME,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT,
        FOREIGN KEY (role_id) REFERENCES roles(uuid)
      )
    `);
    // // 迁移：若旧表无version列则添加
    // try {
    //   const cols = this.db.prepare(`PRAGMA table_info(robots)`).all() as any[];
    //   if (!cols.some((c: any) => c.name === 'version')) {
    //     this.db.exec(`ALTER TABLE robots ADD COLUMN version TEXT`);
    //   }
    // } catch {}

    // 对话历史表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS conversations (
        uuid INTEGER PRIMARY KEY AUTOINCREMENT,
        robot_id TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        type TEXT CHECK(type IN ('audio', 'text')),
        user_input TEXT NOT NULL,
        ai_response TEXT NOT NULL,
        actions TEXT,
        processing_time INTEGER,
        metadata TEXT,
        FOREIGN KEY (robot_id) REFERENCES robots(uuid)
      )
    `);

    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_conversations_robot_id 
      ON conversations(robot_id);
      
      CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
      ON conversations(timestamp);
    `);

    // 知识库文档表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS knowledge_documents (
        uuid TEXT PRIMARY KEY,
        title TEXT,
        content TEXT NOT NULL,
        category TEXT,
        tags TEXT,
        embedding_vector BLOB,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 系统日志表
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT NOT NULL,
        robot_id TEXT,
        message TEXT NOT NULL,
        stack_trace TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT
      )
    `);

    // 动作执行记录
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS action_logs (
        uuid INTEGER PRIMARY KEY AUTOINCREMENT,
        robot_id TEXT NOT NULL,
        action_name TEXT NOT NULL,
        parameters TEXT,
        status TEXT CHECK(status IN ('success', 'failed', 'rejected')) DEFAULT 'success',
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // 创建索引
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_robots_status ON robots(status);
      CREATE INDEX IF NOT EXISTS idx_conversations_robot_id ON conversations(robot_id);
      CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
      CREATE INDEX IF NOT EXISTS idx_action_logs_robot_id ON action_logs(robot_id);
      CREATE INDEX IF NOT EXISTS idx_action_logs_executed_at ON action_logs(executed_at);
    `);

    console.log('数据库初始化完成');
  }

  // 设置管理
  setSetting(key: string, value: string): void {
    const stmt = this.db.prepare(`
      INSERT INTO settings (key, value, updated_at)
      VALUES (?, ?, datetime('now'))
      ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    `);
    stmt.run(key, value);
  }

  setParam(key: string, value: string): void {
    const stmt = this.db.prepare(`
      INSERT INTO params (key, value, updated_at)
      VALUES (?, ?, datetime('now'))
      ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    `);
    stmt.run(key, value);
  }

  getSetting(key: string): string | undefined {
    const stmt = this.db.prepare(`SELECT value FROM settings WHERE key = ?`);
    const row = stmt.get(key) as { value: string } | undefined;
    return row?.value;
  }

  getParam(key: string): string | undefined {
    const stmt = this.db.prepare(`SELECT value FROM params WHERE key = ?`);
    const row = stmt.get(key) as { value: string } | undefined;
    return row?.value;
  }

  getAllSettings(): Record<string, string> {
    const stmt = this.db.prepare(`SELECT key, value FROM settings`);
    const rows = stmt.all() as { key: string; value: string }[];
    const map: Record<string, string> = {};
    for (const r of rows) map[r.key] = r.value;
    return map;
  }

  getAllParams(): Record<string, string> {
    const stmt = this.db.prepare(`SELECT key, value FROM params`);
    const rows = stmt.all() as { key: string; value: string }[];
    const map: Record<string, string> = {};
    for (const r of rows) map[r.key] = r.value;
    return map;
  }

  // 机器狗管理
  registerRobot(robot: Partial<RobotRecord>): void {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO robots (uuid, name, model, version, ip, group_name, tags, sn, status, last_connected, registered_at, updated_at, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    `);

    stmt.run(
      robot.uuid,
      robot.name || null,
      robot.model || null,
      robot.version || null,
      robot.ip || null,
      (robot as any).group_name || null,
      (robot as any).tags || null,
      (robot as any).sn || null,
      robot.status || 'offline',
      robot.last_connected?.toISOString() || new Date().toISOString(),
      (robot as any).registered_at?.toISOString?.() || null,
      robot.metadata ? JSON.stringify(robot.metadata) : null
    );
  }

  updateRobotStatus(robotId: string, status: 'online' | 'offline' | 'error'): void {
    const stmt = this.db.prepare(`
      UPDATE robots 
      SET status = ?, last_connected = CURRENT_TIMESTAMP 
      WHERE uuid = ?
    `);
    stmt.run(status, robotId);
  }

  updateRobotIP(robotId: string, ip: string): void {
    const stmt = this.db.prepare(`
      UPDATE robots 
      SET ip = ? 
      WHERE uuid = ?
    `);
    stmt.run(ip, robotId);
  }

  getRobot(robotId: string): RobotRecord | undefined {
    const stmt = this.db.prepare('SELECT * FROM robots WHERE uuid = ?');
    const robot = stmt.get(robotId) as RobotRecord | undefined;
    
    // 如果没有IP但metadata中有ip，则迁移
    if (robot && !robot.ip && robot.metadata) {
      try {
        const metadata = typeof robot.metadata === 'string' ? JSON.parse(robot.metadata) : robot.metadata;
        if (metadata && metadata.ip) {
          this.updateRobotIP(robotId, metadata.ip);
          robot.ip = metadata.ip;
          // 从 metadata 中删除 ip
          delete metadata.ip;
          const updateStmt = this.db.prepare('UPDATE robots SET metadata = ? WHERE uuid = ?');
          updateStmt.run(JSON.stringify(metadata), robotId);
        }
      } catch (e) {
        console.error('迁移IP失败:', e);
      }
    }
    
    return robot;
  }

  getAllRobots(): RobotRecord[] {
    const stmt = this.db.prepare('SELECT * FROM robots ORDER BY last_connected DESC');
    return stmt.all() as RobotRecord[];
  }

  // 从metadata迁移IP到ip字段
  migrateIPFromMetadata(): void {
    const stmt = this.db.prepare('SELECT * FROM robots ORDER BY last_connected DESC');
    const robots = stmt.all() as RobotRecord[];
    let migratedCount = 0;
    
    for (const robot of robots) {
      if (!robot.ip && robot.metadata) {
        try {
          const metadata = typeof robot.metadata === 'string' ? JSON.parse(robot.metadata) : robot.metadata;
          if (metadata && metadata.ip) {
            this.updateRobotIP(robot.uuid, metadata.ip);
            // 从 metadata 中删除 ip
            delete metadata.ip;
            const updateStmt = this.db.prepare('UPDATE robots SET metadata = ? WHERE uuid = ?');
            updateStmt.run(JSON.stringify(metadata), robot.uuid);
            migratedCount++;
            console.log(`迁移机器人 ${robot.uuid} 的IP: ${metadata.ip}`);
          }
        } catch (e) {
          console.error(`迁移机器人 ${robot.uuid} 的IP失败:`, e);
        }
      }
    }
    
    if (migratedCount > 0) {
      console.log(`成功迁移 ${migratedCount} 个机器人的IP地址`);
    }
  }

  // 对话记录
  insertConversation(data: Omit<ConversationRecord, 'uuid'>): number {
    const stmt = this.db.prepare(`
      INSERT INTO conversations (robot_id, timestamp, type, user_input, ai_response, actions, processing_time, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const result = stmt.run(
      data.robot_id,
      data.timestamp.toISOString(),
      data.type,
      data.user_input,
      data.ai_response,
      data.actions ? JSON.stringify(data.actions) : null,
      data.processing_time,
      data.metadata ? JSON.stringify(data.metadata) : null
    );

    return result.lastInsertRowid as number;
  }

  getConversationHistory(robotId: string, limit = 50, offset = 0): ConversationRecord[] {
    const stmt = this.db.prepare(`
      SELECT * FROM conversations
      WHERE robot_id = ?
      ORDER BY timestamp DESC
      LIMIT ? OFFSET ?
    `);

    return stmt.all(robotId, limit, offset) as ConversationRecord[];
  }

  updateRobot(uuid: string, data: Partial<RobotRecord>): RobotRecord | undefined {
    const fields: string[] = [];
    const values: any[] = [];
    if (data.name !== undefined) {
      fields.push('name = ?');
      values.push(data.name ?? null);
    }
    if (data.model !== undefined) {
      fields.push('model = ?');
      values.push(data.model ?? null);
    }
    if (data.version !== undefined) {
      fields.push('version = ?');
      values.push(data.version ?? null);
    }
    if (data.ip !== undefined) {
      fields.push('ip = ?');
      values.push(data.ip ?? null);
    }
    if ((data as any).group_name !== undefined) {
      fields.push('group_name = ?');
      values.push((data as any).group_name ?? null);
    }
    if ((data as any).tags !== undefined) {
      fields.push('tags = ?');
      const t = (data as any).tags;
      values.push(Array.isArray(t) ? JSON.stringify(t) : (typeof t === 'string' ? t : null));
    }
    if ((data as any).sn !== undefined) {
      fields.push('sn = ?');
      values.push((data as any).sn ?? null);
    }
    if ((data as any).role_id !== undefined) {
      fields.push('role_id = ?');
      values.push((data as any).role_id ?? null);
    }
    if (data.status !== undefined) {
      fields.push('status = ?');
      values.push(data.status);
    }
    if (data.last_connected !== undefined) {
      fields.push('last_connected = ?');
      values.push(data.last_connected ? data.last_connected.toISOString() : new Date().toISOString());
    }
    if (data.metadata !== undefined) {
      fields.push('metadata = ?');
      values.push(data.metadata ?? null);
    }
    // 始终更新更新时间
    fields.push('updated_at = CURRENT_TIMESTAMP');
    if (fields.length === 0) {
      return this.getRobot(uuid);
    }
    const stmt = this.db.prepare(`UPDATE robots SET ${fields.join(', ')} WHERE uuid = ?`);
    stmt.run(...values, uuid);
    return this.getRobot(uuid);
  }

  deleteRobot(uuid: string): void {
    const deleteConversations = this.db.prepare('DELETE FROM conversations WHERE robot_id = ?');
    const deleteActionLogs = this.db.prepare('DELETE FROM action_logs WHERE robot_id = ?');
    const deleteRobot = this.db.prepare('DELETE FROM robots WHERE uuid = ?');

    const runTransaction = this.db.transaction(() => {
      deleteConversations.run(uuid);
      deleteActionLogs.run(uuid);
      deleteRobot.run(uuid);
    });

    runTransaction();
  }

  // 动作日志
  logAction(robotId: string, actionName: string, parameters: any, status: string): void {
    const stmt = this.db.prepare(`
      INSERT INTO action_logs (robot_id, action_name, parameters, status, executed_at)
      VALUES (?, ?, ?, ?, datetime('now'))
    `);

    stmt.run(robotId, actionName, JSON.stringify(parameters), status);
  }

  // ===== 角色管理 =====
  
  createRole(data: {
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
  }) {
    const stmt = this.db.prepare(`
      INSERT INTO roles (uuid, name, description, llm_provider, llm_model, temperature, system_prompt, voice, intent_strategy, max_history)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      data.uuid,
      data.name,
      data.description || null,
      data.llm_provider || null,
      data.llm_model || null,
      data.temperature !== undefined ? data.temperature : 0.7,
      data.system_prompt || null,
      data.voice || null,
      data.intent_strategy || null,
      typeof data.max_history === 'number' ? data.max_history : 10
    );
    return this.getRole(data.uuid);
  }

  getRole(uuid: string) {
    const stmt = this.db.prepare('SELECT * FROM roles WHERE uuid = ?');
    return stmt.get(uuid) as any;
  }

  getAllRoles() {
    const stmt = this.db.prepare('SELECT * FROM roles ORDER BY created_at DESC');
    return stmt.all() as any[];
  }

  updateRole(uuid: string, data: Partial<{
    name: string;
    description: string;
    llm_provider: string;
    llm_model: string;
    temperature: number;
    system_prompt: string;
    voice: string;
    intent_strategy: string;
    max_history: number;
  }>) {
    const fields: string[] = [];
    const values: any[] = [];

    if (data.name !== undefined) {
      fields.push('name = ?');
      values.push(data.name);
    }
    if (data.description !== undefined) {
      fields.push('description = ?');
      values.push(data.description || null);
    }
    if (data.llm_provider !== undefined) {
      fields.push('llm_provider = ?');
      values.push(data.llm_provider || null);
    }
    if (data.llm_model !== undefined) {
      fields.push('llm_model = ?');
      values.push(data.llm_model || null);
    }
    if (data.temperature !== undefined) {
      fields.push('temperature = ?');
      values.push(data.temperature);
    }
    if (data.system_prompt !== undefined) {
      fields.push('system_prompt = ?');
      values.push(data.system_prompt || null);
    }
    if (data.voice !== undefined) {
      fields.push('voice = ?');
      values.push(data.voice || null);
    }
    if (data.intent_strategy !== undefined) {
      fields.push('intent_strategy = ?');
      values.push(data.intent_strategy || null);
    }
    if ((data as any).max_history !== undefined) {
      fields.push('max_history = ?');
      values.push((data as any).max_history);
    }

    fields.push('updated_at = CURRENT_TIMESTAMP');

    if (fields.length === 1) {
      return this.getRole(uuid);
    }

    const stmt = this.db.prepare(`UPDATE roles SET ${fields.join(', ')} WHERE uuid = ?`);
    stmt.run(...values, uuid);
    return this.getRole(uuid);
  }

  deleteRole(uuid: string) {
    // 解绑所有使用该角色的机器人
    const unbindStmt = this.db.prepare('UPDATE robots SET role_id = NULL WHERE role_id = ?');
    unbindStmt.run(uuid);

    // 删除角色
    const stmt = this.db.prepare('DELETE FROM roles WHERE uuid = ?');
    stmt.run(uuid);
  }

  getRobotsByRole(roleId: string) {
    const stmt = this.db.prepare('SELECT * FROM robots WHERE role_id = ?');
    return stmt.all(roleId) as RobotRecord[];
  }

  // 关闭数据库连接
  close(): void {
    this.db.close();
  }
}

export default DatabaseService;
