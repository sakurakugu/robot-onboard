import { v4 as uuidv4 } from 'uuid';
import DatabaseService from '../../core/database';
import LoggerService from '../../core/logger';
import { CreateRoleDto, RoleRecord, UpdateRoleDto } from './types';

export class RoleService {
  constructor(
    private database: DatabaseService,
    private logger: LoggerService
  ) {}

  /**
   * 创建角色
   */
  createRole(data: CreateRoleDto): RoleRecord {
    try {
      const uuid = uuidv4();
      const role = this.database.createRole({
        uuid,
        name: data.name,
        description: data.description,
        llm_provider: data.llm_provider,
        llm_model: data.llm_model,
        temperature: data.temperature,
        system_prompt: data.system_prompt,
        voice: data.voice,
        intent_strategy: data.intent_strategy,
        max_history: data.max_history
      });
      
      this.logger.info(`角色创建成功: ${uuid}`, { name: data.name });
      return role;
    } catch (error: any) {
      this.logger.error('创建角色失败', error);
      throw new Error(`创建角色失败: ${error.message}`);
    }
  }

  /**
   * 获取所有角色
   */
  getAllRoles(): RoleRecord[] {
    try {
      return this.database.getAllRoles();
    } catch (error: any) {
      this.logger.error('获取角色列表失败', error);
      throw new Error(`获取角色列表失败: ${error.message}`);
    }
  }

  /**
   * 获取角色详情
   */
  getRole(uuid: string): RoleRecord | undefined {
    try {
      return this.database.getRole(uuid);
    } catch (error: any) {
      this.logger.error(`获取角色详情失败: ${uuid}`, error);
      throw new Error(`获取角色详情失败: ${error.message}`);
    }
  }

  /**
   * 更新角色
   */
  updateRole(uuid: string, data: UpdateRoleDto): RoleRecord | undefined {
    try {
      const role = this.database.updateRole(uuid, data);
      this.logger.info(`角色更新成功: ${uuid}`);
      return role;
    } catch (error: any) {
      this.logger.error(`更新角色失败: ${uuid}`, error);
      throw new Error(`更新角色失败: ${error.message}`);
    }
  }

  /**
   * 删除角色
   */
  deleteRole(uuid: string): void {
    try {
      this.database.deleteRole(uuid);
      this.logger.info(`角色删除成功: ${uuid}`);
    } catch (error: any) {
      this.logger.error(`删除角色失败: ${uuid}`, error);
      throw new Error(`删除角色失败: ${error.message}`);
    }
  }

  /**
   * 获取使用该角色的机器人列表
   */
  getRobotsByRole(roleId: string) {
    try {
      return this.database.getRobotsByRole(roleId);
    } catch (error: any) {
      this.logger.error(`获取角色绑定的机器人失败: ${roleId}`, error);
      throw new Error(`获取角色绑定的机器人失败: ${error.message}`);
    }
  }
}
