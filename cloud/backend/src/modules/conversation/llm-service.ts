import axios from 'axios';
import config from '../../config';
import { LLMOptions, LLMResponse, Message } from '../../types';

export class LLMService {
  constructor() {}

  /**
   * 调用LLM进行对话
   */
  async chat(messages: Message[], options?: Partial<LLMOptions>): Promise<LLMResponse> {
    const provider = config.llm.provider;
    switch (provider) {
      case 'openai':
        return this.chatOpenAI(messages, options);
      case 'bigmodel':
        return this.chatBigModel(messages, options);
      default:
        throw new Error(`不支持的LLM提供商: ${provider}`);
    }
  }

  /**
   * OpenAI API调用
   */
  private async chatOpenAI(messages: Message[], options?: Partial<LLMOptions>): Promise<LLMResponse> {
    const { openai } = config.llm;
    if (!openai?.apiKey) {
      throw new Error('OpenAI API密钥未配置');
    }

    const baseUrl = openai.baseUrl || 'https://api.openai.com/v1';
    const url = `${baseUrl}/chat/completions`;

    try {
      const response = await axios.post(
        url,
        {
          model: options?.model || openai.model || 'gpt-4',
          messages: messages.map(m => ({
            role: m.role,
            content: m.content,
          })),
          temperature: options?.temperature || 0.7,
          max_tokens: options?.maxTokens || 1000,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${openai.apiKey}`,
          },
          timeout: 30000,
        }
      );

      const choice = response.data.choices[0];
      return {
        content: choice.message.content,
        finishReason: choice.finish_reason,
        usage: {
          promptTokens: response.data.usage.prompt_tokens,
          completionTokens: response.data.usage.completion_tokens,
          totalTokens: response.data.usage.total_tokens,
        },
      };
    } catch (error: any) {
      console.error('OpenAI API调用失败:', error.response?.data || error.message);
      throw new Error(`LLM调用失败: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  /**
   * BigModel API调用 (GLM系列)
   */
  private async chatBigModel(messages: Message[], options?: Partial<LLMOptions>): Promise<LLMResponse> {
    const big = config.llm.bigmodel;
    if (!big?.apiKey) {
      throw new Error('BigModel API密钥未配置');
    }
    const baseUrl = big.baseUrl || 'https://open.bigmodel.cn/api/paas/v4/chat/completions';
    const url = baseUrl;
    try {
      const response = await axios.post(
        url,
        {
          model: options?.model || big.model || 'glm-4.5-flash',
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          temperature: options?.temperature ?? 0.7,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${big.apiKey}`,
          },
          timeout: 30000,
        }
      );
      const choice = response.data?.choices?.[0];
      const msg = choice?.message || response.data?.data?.choices?.[0]?.message;
      return {
        content: msg?.content || '',
        finishReason: choice?.finish_reason || 'stop',
        usage: {
          promptTokens: response.data?.usage?.prompt_tokens || 0,
          completionTokens: response.data?.usage?.completion_tokens || 0,
          totalTokens: response.data?.usage?.total_tokens || 0,
        },
      };
    } catch (error: any) {
      const errorData = error.response?.data;
      console.error('BigModel API调用失败:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: errorData,
        message: error.message
      });
      
      // 提取错误信息
      let errorMessage = error.message;
      if (errorData?.error) {
        errorMessage = errorData.error.message || errorData.error.code || JSON.stringify(errorData.error);
      } else if (typeof errorData === 'string') {
        errorMessage = errorData;
      } else if (errorData?.message) {
        errorMessage = errorData.message;
      }
      
      throw new Error(`LLM调用失败: ${errorMessage}`);
    }
  }
/**
   * 构建系统提示词
   */
  getSystemPrompt(): string {
    return `你是一只可爱的机器狗AI助手。你可以：
1. 与用户进行自然对话
2. 执行一些基本动作来配合对话

可用动作列表：
- stand_up: 站起来
- sit_down: 坐下、蹲下、趴下
- turn_left/turn_right: 转向
- shake_hand: 握手
- wave: 挥手
- nod: 点头
- dance: 跳舞
- walk_forward: 前进，最多3步
- walk_backward: 后退，最多3步

当用户要求你做动作时，请在回复中使用{{action=动作名称}}或{{action=动作名称,参数名=值}}格式，例如：
- 用户："坐下" -> 回复："好的主人{{action=sit_down}}"
- 用户："向前走两步" -> 回复："好的，我来走两步{{action=walk_forward,steps=2}}"
- 用户："转个圈" -> 回复："好的，我来转一圈{{action=turn_left,angle=360}}"

注意事项：
1. 保持友好、可爱的语气
2. 动作要安全，不要让我走太多步
3. 如果用户要求危险动作，要委婉拒绝
4. 一次回复中可以包含多个动作标记`;
  }
}

export default LLMService;
