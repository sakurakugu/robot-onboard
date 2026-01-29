import { spawn } from 'child_process';
import net from 'net';
import path from 'path';
import { v7 as uuidv7 } from 'uuid';
import DatabaseService from '../../core/database';
import LoggerService from '../../core/logger';
import { formatTimestamp } from '../../core/utils/datetime';
import { RobotRecord } from '../../types';

export class RobotService {
  constructor(
    private database: DatabaseService,
    private logger: LoggerService
  ) {}

  transformRobot(r: RobotRecord | undefined) {
    if (!r) return r;
    let meta: any = {};
    try {
      meta = r.metadata ? JSON.parse(r.metadata) : {};
    } catch {
      meta = {};
    }
    const {
      ai_temperature,
      ai_system_prompt,
      ai_voice,
      ai_intent,
      ai_role_name,
      lastStatus,
      lastStatusTime
    } = meta || {};
    const parsedTags = (() => {
      if (typeof r.tags === 'string') {
        try {
          const arr = JSON.parse(r.tags);
          return Array.isArray(arr) ? arr : [];
        } catch {
          return [];
        }
      }
      return [];
    })();
    return {
      ...r,
      ip: r.ip || null,
      robot_ip: r.ip || null,
      group_name: r.group_name ?? null,
      sn: r.sn ?? null,
      tags: parsedTags,
      ai_temperature,
      ai_system_prompt,
      ai_voice,
      ai_intent,
      ai_role_name,
      lastStatus,
      lastStatusTime,
    };
  }

  getAllRobots() {
    return this.database.getAllRobots().map(r => this.transformRobot(r as RobotRecord));
  }

  getRobot(uuid: string) {
    const robot = this.database.getRobot(uuid);
    return this.transformRobot(robot as RobotRecord);
  }

  getGroups() {
    const groups = new Set<string>();
    for (const r of this.database.getAllRobots()) {
      if (r.group_name && typeof r.group_name === 'string') {
        groups.add(r.group_name);
      }
    }
    return Array.from(groups).sort();
  }

  async createRobot(data: {
    name?: string;
    ip?: string;
    robot_ip?: string;
    group_name?: string;
    model?: string;
    status?: string;
    sn?: string;
    tags?: string[] | string;
  }) {
    const finalIp = data.ip || data.robot_ip || null;
    let finalUuid: string | null = null;

    if (finalIp) {
      // SSH初始化流程
      const pythonScript = path.resolve(__dirname, '../../core/utils/ssh_helper.py');
      
      // 1) 测试SSH连通性
      const canSsh = await this.testSSHConnection(pythonScript, finalIp);
      if (!canSsh) {
        throw new Error(`无法通过SSH连接到 ${finalIp}`);
      }

      // 2) 创建远程目录并读取UUID
      this.logger.info(`创建远程目录并检查UUID...`);
      const remoteInitCmd = [
        'mkdir -p /home/firefly/sparkrobot/robot-agent',
        'mkdir -p /home/firefly/sparkrobot/config',
        'if [ -f /home/firefly/sparkrobot/config/config.toml ]; then grep "^uuid" /home/firefly/sparkrobot/config/config.toml | cut -d"=" -f2 | tr -d \' \"\' | xargs; fi',
      ].join(' && ');

      const remoteUuidRaw = await this.executeSSHCommand(pythonScript, finalIp, remoteInitCmd);
      let robotUuid: string | null = null;

      if (remoteUuidRaw && remoteUuidRaw.length > 0) {
        const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (uuidPattern.test(remoteUuidRaw)) {
          robotUuid = remoteUuidRaw;
          this.logger.info(`从机器人读取到UUID: ${robotUuid}`);
        }
      }

      if (!robotUuid) {
        robotUuid = uuidv7();
        this.logger.info(`机器人没有UUID，生成新UUID: ${robotUuid}`);
        
        const configToml = `# 火花机器人配置文件\n# 生成于 ${formatTimestamp()}\n\nuuid = "${robotUuid}"\n`;
        const wrote = await this.writeSSHFile(pythonScript, finalIp, '/home/firefly/sparkrobot/config/config.toml', configToml);
        if (!wrote) {
          throw new Error('写入远程UUID配置失败');
        }
        this.logger.info('已将UUID写入机器人配置文件');
      }

      finalUuid = robotUuid;

      // 3) 复制客户端代码
      const clientPath = path.resolve(__dirname, '../../../client');
      this.logger.info(`Client path: ${clientPath}`);
      
      const copyResult = await this.copyToRobot(pythonScript, finalIp, clientPath, '/home/firefly/sparkrobot/robot-agent');
      if (!copyResult.success) {
        throw new Error(`复制客户端代码到机器狗失败: ${copyResult.error || '未知错误'}`);
      }

      this.logger.info(`机器人 ${finalIp} 初始化完成，UUID: ${finalUuid}`);
    }

    const uuid = finalUuid ?? uuidv7();
    this.logger.info(`准备写入数据库，UUID: ${uuid}`);

    const metadata = {};
    this.database.registerRobot({
      uuid,
      name: data.name,
      model: data.model,
      ip: finalIp ?? undefined,
      group_name: data.group_name || null,
      sn: data.sn || null,
      tags: Array.isArray(data.tags) ? JSON.stringify(data.tags) : (typeof data.tags === 'string' ? data.tags : null),
      status: (data.status as any) || 'offline',
      last_connected: new Date(),
      registered_at: new Date(),
      metadata: metadata as any,
    });

    return this.getRobot(uuid);
  }

  updateRobot(uuid: string, data: any) {
    const existing = this.database.getRobot(uuid);
    if (!existing) {
      throw new Error('机器人不存在');
    }

    let meta: any = {};
    try {
      meta = existing.metadata ? JSON.parse(existing.metadata) : {};
    } catch {
      meta = {};
    }

    if (data.ai_temperature !== undefined) meta.ai_temperature = data.ai_temperature;
    if (data.ai_system_prompt !== undefined) meta.ai_system_prompt = data.ai_system_prompt || '';
    if (data.ai_voice !== undefined) meta.ai_voice = data.ai_voice || '';
    if (data.ai_intent !== undefined) meta.ai_intent = data.ai_intent || '';
    if (data.ai_role_name !== undefined) meta.ai_role_name = data.ai_role_name || '';

    const updated = this.database.updateRobot(uuid, {
      name: data.name !== undefined ? data.name : existing.name,
      model: data.model !== undefined ? data.model : existing.model,
      ip: data.ip !== undefined ? data.ip : existing.ip,
      group_name: data.group_name !== undefined ? data.group_name : existing.group_name,
      sn: data.sn !== undefined ? data.sn : existing.sn,
      tags: data.tags !== undefined ? (Array.isArray(data.tags) ? JSON.stringify(data.tags) : (typeof data.tags === 'string' ? data.tags : existing.tags)) : existing.tags,
      status: data.status !== undefined ? data.status : existing.status,
      metadata: JSON.stringify(meta),
    });

    return this.transformRobot(updated as RobotRecord);
  }

  deleteRobot(uuid: string) {
    this.database.deleteRobot(uuid);
  }

  async testConnection(uuid: string): Promise<{ connected: boolean; message: string }> {
    const robot = this.database.getRobot(uuid);
    if (!robot) {
      throw new Error('机器人不存在');
    }

    let robotIp: string | null = robot.ip || null;
    if (!robotIp) {
      try {
        const meta = robot.metadata ? JSON.parse(robot.metadata) : {};
        robotIp = meta.robot_ip || null;
      } catch {
        robotIp = null;
      }
    }

    if (!robotIp) {
      throw new Error('缺少机器人IP');
    }

    // Ping测试
    const pingOk = await new Promise<boolean>((resolve) => {
      const p = spawn('ping', ['-c', '1', '-W', '2', robotIp!]);
      let hadError = false;
      p.on('error', () => {
        hadError = true;
        resolve(false);
      });
      p.on('close', (code) => {
        resolve(!hadError && code === 0);
      });
    });

    if (!pingOk) {
      return { connected: false, message: `网络不可达: ${robotIp}` };
    }

    // SSH端口测试
    const sshReachable = await new Promise<boolean>((resolve) => {
      const socket = net.createConnection({ host: robotIp!, port: 22 });
      const timer = setTimeout(() => {
        try { socket.destroy(); } catch {}
        resolve(false);
      }, 3000);
      socket.on('connect', () => {
        clearTimeout(timer);
        try { socket.destroy(); } catch {}
        resolve(true);
      });
      socket.on('error', () => {
        clearTimeout(timer);
        try { socket.destroy(); } catch {}
        resolve(false);
      });
      socket.on('timeout', () => {
        clearTimeout(timer);
        try { socket.destroy(); } catch {}
        resolve(false);
      });
    });

    if (sshReachable) {
      return { connected: true, message: `SSH端口可达: ${robotIp}` };
    }

    return { connected: false, message: `SSH端口不可达: ${robotIp}` };
  }

  async connectRobot(uuid: string) {
    const robot = this.database.getRobot(uuid);
    if (!robot) {
      throw new Error('机器人不存在');
    }

    let robotIp: string | null = robot.ip || null;
    if (!robotIp) {
      try {
        const meta = robot.metadata ? JSON.parse(robot.metadata) : {};
        robotIp = meta.robot_ip || null;
      } catch {
        robotIp = null;
      }
    }

    if (!robotIp) {
      throw new Error('缺少机器人IP');
    }

    const pythonScript = path.resolve(__dirname, '../../core/utils/ssh_helper.py');
    const ok = await this.testSSHConnection(pythonScript, robotIp);
    
    if (!ok) {
      throw new Error('连接失败');
    }

    this.database.updateRobotStatus(uuid, 'online');
    return this.getRobot(uuid);
  }

  async updateFirmware(uuid: string) {
    const robot = this.database.getRobot(uuid);
    if (!robot) {
      throw new Error('机器人不存在');
    }

    let robotIp: string | null = robot.ip || null;
    if (!robotIp) {
      try {
        const meta = robot.metadata ? JSON.parse(robot.metadata) : {};
        robotIp = meta.robot_ip || null;
      } catch {
        robotIp = null;
      }
    }

    if (!robotIp) {
      throw new Error('缺少机器人IP地址');
    }

    const pythonScript = path.resolve(__dirname, '../../core/utils/ssh_helper.py');

    // 测试连接
    this.logger.info(`测试连接到 ${robotIp}...`);
    const canConnect = await this.testSSHConnection(pythonScript, robotIp);
    if (!canConnect) {
      throw new Error(`无法连接到机器人 ${robotIp}`);
    }

    // 创建远程目录
    this.logger.info('创建远程目录...');
    const mkdirCmd = 'mkdir -p /home/firefly/sparkrobot/robot-agent && mkdir -p /home/firefly/sparkrobot/config';
    try {
      await this.executeSSHCommand(pythonScript, robotIp, mkdirCmd);
    } catch {
      throw new Error('创建远程目录失败');
    }

    // 复制客户端代码
    this.logger.info('开始复制客户端代码...');
    const clientPath = path.resolve(__dirname, '../../../../../client');
    const copyResult = await this.copyToRobot(pythonScript, robotIp, clientPath, '/home/firefly/sparkrobot/robot-agent');
    
    if (!copyResult.success) {
      throw new Error(`复制客户端代码失败: ${copyResult.error || '未知错误'}`);
    }

    this.logger.info('固件更新成功');
    return { robotIp };
  }

  getLogHistory(uuid: string, limit: number = 5) {
    const robot = this.database.getRobot(uuid);
    if (!robot) {
      throw new Error('机器人不存在');
    }

    let meta: any = {};
    try {
      meta = robot.metadata ? JSON.parse(robot.metadata) : {};
    } catch {
      meta = {};
    }

    const list = Array.isArray(meta.logUploadHistory) ? meta.logUploadHistory : [];
    return list.slice(0, limit);
  }

  addLogUploadRecord(uuid: string, data: { from?: string; to?: string; logType?: string }) {
    const robot = this.database.getRobot(uuid);
    if (!robot) {
      throw new Error('机器人不存在');
    }

    let meta: any = {};
    try {
      meta = robot.metadata ? JSON.parse(robot.metadata) : {};
    } catch {
      meta = {};
    }

    const now = new Date();
    const record = {
      id: uuidv7(),
      time: now.toISOString(),
      logType: ['robot', 'app', 'all'].includes(String(data.logType)) ? String(data.logType) : 'all',
      size: 0,
      range: { from: data.from || null, to: data.to || null },
    };

    const prev = Array.isArray(meta.logUploadHistory) ? meta.logUploadHistory : [];
    const next = [record, ...prev].slice(0, 20);
    meta.logUploadHistory = next;
    
    this.database.updateRobot(uuid, { metadata: JSON.stringify(meta) });
    return record;
  }

  // 私有辅助方法
  private async testSSHConnection(pythonScript: string, ip: string): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      const p = spawn('python3', [pythonScript, 'test', ip]);
      let stdout = '';
      p.stdout.on('data', (d) => { stdout += d.toString(); });
      p.on('error', () => resolve(false));
      p.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(stdout);
            resolve(result.success && result.connected);
          } catch {
            resolve(false);
          }
        } else {
          resolve(false);
        }
      });
    });
  }

  private async executeSSHCommand(pythonScript: string, ip: string, command: string): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      const p = spawn('python3', [pythonScript, 'exec', ip, command]);
      let stdout = '';
      p.stdout.on('data', (d) => { stdout += d.toString(); });
      p.on('error', (e) => reject(e));
      p.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(stdout);
            if (result.success) {
              resolve(result.output.trim());
            } else {
              reject(new Error(result.error || '远程命令执行失败'));
            }
          } catch (e) {
            reject(new Error('解析输出失败'));
          }
        } else {
          reject(new Error('远程命令执行失败'));
        }
      });
    });
  }

  private async writeSSHFile(pythonScript: string, ip: string, remotePath: string, content: string): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      const p = spawn('python3', [pythonScript, 'write', ip, remotePath, content]);
      let stdout = '';
      p.stdout.on('data', (d) => { stdout += d.toString(); });
      p.on('error', () => resolve(false));
      p.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(stdout);
            resolve(result.success);
          } catch {
            resolve(false);
          }
        } else {
          resolve(false);
        }
      });
    });
  }

  private async copyToRobot(pythonScript: string, ip: string, localPath: string, remotePath: string): Promise<{ success: boolean; error?: string }> {
    return new Promise<{ success: boolean; error?: string }>((resolve) => {
      const p = spawn('python3', [pythonScript, 'copy', ip, localPath, remotePath]);
      let stdout = '';
      let stderr = '';
      p.stdout.on('data', (d) => { stdout += d.toString(); });
      p.stderr.on('data', (d) => { 
        stderr += d.toString();
        console.log(`[SSH] ${d.toString().trim()}`);
      });
      p.on('error', (err) => {
        console.error(`[ERROR] spawn error:`, err);
        resolve({ success: false, error: err.message });
      });
      p.on('close', (code) => {
        console.log(`[INFO] Copy process exit code: ${code}`);
        if (code === 0) {
          try {
            const result = JSON.parse(stdout);
            resolve(result);
          } catch (e) {
            console.error(`[ERROR] JSON parse error:`, e, `stdout:`, stdout);
            resolve({ success: false, error: '解析输出失败' });
          }
        } else {
          resolve({ success: false, error: stderr || '复制失败' });
        }
      });
    });
  }
}
