import { Request, Response } from 'express';
import { ConversationService } from './service';
import DatabaseService from '../../core/database';

export class ConversationController {
  constructor(
    private conversationService: ConversationService,
    private database: DatabaseService
  ) {}

  private normalizeParam = (v: unknown): string =>
    Array.isArray(v) ? String(v[0]) : String(v ?? '');

  /**
   * 获取对话历史
   */
  async getHistory(req: Request, res: Response) {
    try {
      const robotId = this.normalizeParam((req.params as any).robotId);
      const limit = parseInt(req.query.limit as string) || 50;
      const offset = parseInt(req.query.offset as string) || 0;

      const conversations = this.conversationService.getHistory(robotId, limit, offset);

      res.json({
        success: true,
        data: {
          conversations,
          limit,
          offset,
        },
      });
    } catch (error: any) {
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  }

  /**
   * 发送文本到指定机器狗（由前端控制面调用）
   */
  async sendCommand(req: Request, res: Response) {
    try {
      const robotId = this.normalizeParam((req.params as any).robotId);
      const { text } = req.body || {};
      if (typeof text !== 'string' || text.trim().length === 0) {
        return res.status(400).json({ success: false, error: '缺少文本内容' });
      }

      // 记录到对话历史（标记为控制端直接下发）
      this.database.insertConversation({
        robot_id: robotId,
        timestamp: new Date(),
        type: 'text',
        user_input: `[controller] ${String(text)}`,
        ai_response: String(text),
        actions: JSON.stringify([]),
        processing_time: 0,
        metadata: JSON.stringify({ from: 'controller' }),
      });

      res.json({ success: true });
    } catch (error: any) {
      res.status(500).json({ success: false, error: error.message });
    }
  }
}
