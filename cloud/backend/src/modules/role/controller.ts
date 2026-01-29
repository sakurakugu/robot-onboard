import { Request, Response } from 'express';
import { RoleService } from './service';

export class RoleController {
  constructor(private roleService: RoleService) {}
  private normalizeParam = (v: unknown): string =>
    Array.isArray(v) ? String(v[0]) : String(v ?? '');

  /**
   * 创建角色
   */
  async createRole(req: Request, res: Response) {
    try {
      const data = req.body;
      if (!data.name) {
        return res.status(400).json({ success: false, error: '角色名称不能为空' });
      }
      
      const role = this.roleService.createRole(data);
      res.status(201).json({ success: true, data: role });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 获取所有角色
   */
  async getAllRoles(req: Request, res: Response) {
    try {
      const roles = this.roleService.getAllRoles();
      res.json({ success: true, data: roles });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 获取角色详情
   */
  async getRole(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const role = this.roleService.getRole(uuid);
      
      if (!role) {
        return res.status(404).json({ success: false, error: '角色不存在' });
      }
      
      res.json({ success: true, data: role });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 更新角色
   */
  async updateRole(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const data = req.body;
      
      const role = this.roleService.updateRole(uuid, data);
      
      if (!role) {
        return res.status(404).json({ success: false, error: '角色不存在' });
      }
      
      res.json({ success: true, data: role });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 删除角色
   */
  async deleteRole(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      this.roleService.deleteRole(uuid);
      res.json({ success: true, message: '角色删除成功' });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 获取角色绑定的机器人
   */
  async getRobotsByRole(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const robots = this.roleService.getRobotsByRole(uuid);
      res.json({ success: true, data: robots });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }
}
