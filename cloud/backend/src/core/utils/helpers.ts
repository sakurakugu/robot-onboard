import { v7 as uuidv7 } from 'uuid';

export { uuidv7 };

/**
 * 解析动作指令
 * 格式：{{action=action_name}} 或 {{action=action_name,param=value}}
 */
export function parseActions(text: string): Array<{ name: string; parameters: Record<string, any> }> {
  const actions: Array<{ name: string; parameters: Record<string, any> }> = [];
  const actionRegex = /\{\{action=([a-zA-Z_][a-zA-Z0-9_]*)((?:,[a-zA-Z_][a-zA-Z0-9_]*=[^,}]+)*)\}\}/g;
  let match;

  while ((match = actionRegex.exec(text)) !== null) {
    const actionName = match[1];
    const paramsStr = match[2];

    try {
      const parameters: Record<string, any> = {};
      
      // 解析参数
      if (paramsStr) {
        const paramPairs = paramsStr.slice(1).split(','); // 去掉开头的逗号
        paramPairs.forEach(pair => {
          const [key, value] = pair.split('=').map(s => s.trim());
          if (key && value !== undefined) {
            parameters[key] = isNaN(Number(value)) ? value : Number(value);
          }
        });
      }

      actions.push({ name: actionName, parameters });
    } catch (error) {
      console.error(`解析动作失败: ${match[0]}`, error);
    }
  }

  return actions;
}

/**
 * 移除文本中的动作标记
 */
export function removeActionTags(text: string): string {
  return text.replace(/\{\{action=([a-zA-Z_][a-zA-Z0-9_]*)((?:,[a-zA-Z_][a-zA-Z0-9_]*=[^,}]+)*)\}\}/g, '').trim();
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(date: Date): string {
  return date.toISOString();
}

/**
 * 计算处理时间
 */
export function calculateProcessingTime(startTime: number): number {
  return Date.now() - startTime;
}

/**
 * Base64编码
 */
export function base64Encode(buffer: Buffer): string {
  return buffer.toString('base64');
}

/**
 * Base64解码
 */
export function base64Decode(str: string): Buffer {
  return Buffer.from(str, 'base64');
}

/**
 * 验证机器狗ID格式
 */
export function isValidRobotId(id: string): boolean {
  // UUID格式验证
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(id);
}

/**
 * 限流器
 */
export class RateLimiter {
  private requests: Map<string, number[]> = new Map();
  private maxRequests: number;
  private windowMs: number;

  constructor(maxRequests: number, windowMs: number) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
  }

  check(key: string): boolean {
    const now = Date.now();
    const timestamps = this.requests.get(key) || [];
    
    // 移除过期的请求
    const validTimestamps = timestamps.filter(t => now - t < this.windowMs);
    
    if (validTimestamps.length >= this.maxRequests) {
      return false;
    }
    
    validTimestamps.push(now);
    this.requests.set(key, validTimestamps);
    return true;
  }

  reset(key: string): void {
    this.requests.delete(key);
  }
}

/**
 * 延迟函数
 */
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
