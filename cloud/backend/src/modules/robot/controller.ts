import { Request, Response } from 'express';
import { RobotService } from './service';

export class RobotController {
  constructor(private robotService: RobotService) {}

  private normalizeParam = (v: unknown): string =>
    Array.isArray(v) ? String(v[0]) : String(v ?? '');

  /**
   * 获取所有机器狗列表
   */
  async getAllRobots(req: Request, res: Response) {
    try {
      const robots = this.robotService.getAllRobots();
      res.json({
        success: true,
        data: { robots },
      });
    } catch (error: any) {
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  }

  /**
   * 获取机器狗分组
   */
  async getGroups(req: Request, res: Response) {
    try {
      const groups = this.robotService.getGroups();
      res.json({ success: true, data: { groups } });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 获取指定机器狗信息
   */
  async getRobot(req: Request, res: Response) {
    try {
      const robotId = this.normalizeParam((req.params as any).robotId || (req.params as any).uuid);
      const robot = this.robotService.getRobot(robotId);
      if (!robot) {
        return res.status(404).json({
          success: false,
          error: '机器狗不存在',
        });
      }
      res.json({
        success: true,
        data: robot,
      });
    } catch (error: any) {
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  }

  /**
   * 创建机器人
   */
  async createRobot(req: Request, res: Response) {
    try {
      const created = await this.robotService.createRobot(req.body || {});
      res.json({ success: true, data: created });
    } catch (error: any) {
      const status = error.message.includes('无法') ? 400 : 500;
      res.status(status).json({ success: false, error: error.message });
    }
  }

  /**
   * 更新机器人
   */
  async updateRobot(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const updated = this.robotService.updateRobot(uuid, req.body || {});
      res.json({ success: true, data: updated });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : 500;
      res.status(status).json({ success: false, error: error.message });
    }
  }

  /**
   * 删除机器人
   */
  async deleteRobot(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      this.robotService.deleteRobot(uuid);
      res.json({ success: true });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * 测试机器人连接
   */
  async testConnection(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const result = await this.robotService.testConnection(uuid);
      res.json({ 
        success: result.connected, 
        connected: result.connected,
        message: result.message 
      });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : (error.message.includes('缺少') ? 400 : 500);
      res.status(status).json({ success: false, connected: false, error: error.message });
    }
  }

  /**
   * 连接机器人
   */
  async connectRobot(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const updated = await this.robotService.connectRobot(uuid);
      res.json({ success: true, data: updated, message: '连接成功' });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : (error.message.includes('缺少') ? 400 : 500);
      res.status(status).json({ success: false, error: error.message });
    }
  }

  /**
   * 更新机器人固件
   */
  async updateFirmware(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const result = await this.robotService.updateFirmware(uuid);
      res.json({ 
        success: true, 
        message: '客户端代码已成功更新到机器人',
        data: result
      });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : (error.message.includes('缺少') ? 400 : 500);
      res.status(status).json({ success: false, error: error.message });
    }
  }

  /**
   * 获取日志上传历史
   */
  async getLogHistory(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const limit = Math.max(1, Math.min(50, parseInt(req.query.limit as string) || 5));
      const records = this.robotService.getLogHistory(uuid, limit);
      res.json({ success: true, data: { records } });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : 500;
      res.status(status).json({ success: false, error: error.message });
    }
  }

  /**
   * 上传日志
   */
  async uploadLog(req: Request, res: Response) {
    try {
      const uuid = this.normalizeParam((req.params as any).uuid);
      const { from, to, logType } = req.body || {};
      const record = this.robotService.addLogUploadRecord(uuid, { from, to, logType });
      res.json({ success: true, data: { record } });
    } catch (error: any) {
      const status = error.message === '机器人不存在' ? 404 : 500;
      res.status(status).json({ success: false, error: error.message });
    }
  }
}
