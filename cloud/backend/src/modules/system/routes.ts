import { Request, Response, Router } from 'express';
import os from 'os';
import DatabaseService from '../../core/database';
import { formatTimestamp } from '../../core/utils/datetime';
import WebSocketService from '../websocket/service';

export function createSystemRoutes(
  database: DatabaseService,
  websocketService: WebSocketService
): Router {
  const router = Router();

  /**
   * 获取系统状态
   */
  router.get('/status', (req: Request, res: Response) => {
    try {
      const onlineRobots = websocketService.getOnlineCount();
      const allRobots = database.getAllRobots();

      res.json({
        success: true,
        data: {
          onlineRobots,
          totalRobots: allRobots.length,
          timestamp: formatTimestamp(),
        },
      });
    } catch (error: any) {
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  });

  /**
   * 健康检查
   */
  router.get('/health', (req: Request, res: Response) => {
    res.json({
      success: true,
      data: {
        status: 'healthy',
        timestamp: formatTimestamp(),
      },
    });
  });

  /**
   * 获取本机IP
   */
  router.get('/network/local-ip', (req: Request, res: Response) => {
    try {
      const interfaces = os.networkInterfaces();
      const addresses: string[] = [];
      Object.keys(interfaces).forEach((ifname) => {
        interfaces[ifname]?.forEach((iface) => {
          if (iface.family !== 'IPv4' || iface.internal) return;
          addresses.push(iface.address);
        });
      });
      const ip = addresses[0] || '';
      res.json({ success: true, data: { ip, all: addresses } });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  /**
   * 检查更新
   */
  router.get('/updates/check', (req: Request, res: Response) => {
    try {
      const robotId = req.query.robotId as string;
      const robot = robotId ? database.getRobot(robotId) : undefined;
      res.json({
        success: true,
        data: {
          checkedAt: new Date().toISOString(),
          app: { currentVersion: '', latestVersion: '', hasUpdate: false },
          firmware: { currentVersion: robot?.version || '', latestVersion: robot?.version || '', hasUpdate: false },
        },
      });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  /**
   * 升级APP
   */
  router.post('/updates/upgrade/app', async (req: Request, res: Response) => {
    try {
      res.json({ success: true, message: '已触发APP升级（预留接口）' });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  });

  return router;
}
