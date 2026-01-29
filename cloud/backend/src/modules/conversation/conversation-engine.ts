import { parseActions, removeActionTags } from '../../core/utils/helpers';
import { AIResponse, ConversationContext, Message } from '../../types';
import ActionController from './action-controller';
import LLMService from './llm-service';

class ConversationEngine {
  private llmService: LLMService;
  private actionController: ActionController;
  private conversationHistory: Map<string, Message[]>;

  constructor() {
    this.llmService = new LLMService();
    this.actionController = new ActionController();
    this.conversationHistory = new Map();
  }

  /**
   * 处理用户消息
   */
  async processMessage(
    robotId: string,
    userMessage: string,
    context?: Partial<ConversationContext>
  ): Promise<AIResponse> {
    const startTime = Date.now();

    try {
      // 获取或初始化对话历史
      let history = this.conversationHistory.get(robotId) || [];
      const maxHistory = context?.maxHistory || 10;

      // 保持历史记录在限制范围内
      if (history.length > maxHistory * 2) {
        history = history.slice(-maxHistory * 2);
      }

      // 构建消息列表
      const messages: Message[] = [
        {
          role: 'system',
          content: context?.systemPrompt || this.llmService.getSystemPrompt(),
          timestamp: new Date(),
        },
        ...history,
        {
          role: 'user',
          content: userMessage,
          timestamp: new Date(),
        },
      ];

      // 调用LLM
      const llmResponse = await this.llmService.chat(messages, {
        model: context?.model || '',
        temperature: context?.temperature
      });
      const responseText = llmResponse.content;

      // 解析动作指令
      const actions = parseActions(responseText);

      // 移除动作标记，得到纯文本回复
      const cleanText = removeActionTags(responseText);

      // 安全检查动作
      const { validActions, rejectedActions } = this.actionController.validateActions(
        robotId,
        actions
      );

      // 如果有被拒绝的动作，在回复中说明
      let finalText = cleanText;
      if (rejectedActions.length > 0) {
        const rejectedNames = rejectedActions.map(r => r.action.name).join('、');
        finalText += `\n\n（注意：动作"${rejectedNames}"因安全原因无法执行）`;
      }

      // 更新对话历史
      history.push(
        {
          role: 'user',
          content: userMessage,
          timestamp: new Date(),
        },
        {
          role: 'assistant',
          content: responseText,
          timestamp: new Date(),
        }
      );
      this.conversationHistory.set(robotId, history);

      const responseTime = Date.now() - startTime;

      return {
        text: finalText,
        actions: validActions,
        metadata: {
          model: llmResponse.finishReason,
          tokensUsed: llmResponse.usage.totalTokens,
          responseTime,
        },
      };
    } catch (error: any) {
      console.error('处理消息失败:', error);
      throw error;
    }
  }

  /**
   * 清除对话历史
   */
  clearHistory(robotId: string): void {
    this.conversationHistory.delete(robotId);
  }

  /**
   * 获取对话历史
   */
  getHistory(robotId: string): Message[] {
    return this.conversationHistory.get(robotId) || [];
  }
}

export default ConversationEngine;
