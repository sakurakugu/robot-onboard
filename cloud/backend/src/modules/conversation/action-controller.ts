import { RateLimiter } from '../../core/utils/helpers';
import { Action, SafetyCheckResult, SafetyRule } from '../../types';

export class ActionController {
  // 动作白名单
  private readonly ALLOWED_ACTIONS = new Set([
    'stand_up',
    'sit_down',
    'turn_left',
    'turn_right',
    'shake_hand',
    'wave',
    'nod',
    'dance',
    'walk_forward',
    'walk_backward',
  ]);

  // 安全规则
  private readonly SAFETY_RULES: SafetyRule[] = [
    { action: 'walk_forward', maxValue: 3 },
    { action: 'walk_backward', maxValue: 3 },
    { action: 'turn_left', maxValue: 720 },
    { action: 'turn_right', maxValue: 720 },
  ];

  // 频率限制器 (每分钟最多10次动作)
  private rateLimiter: RateLimiter;

  constructor() {
    this.rateLimiter = new RateLimiter(10, 60000); // 10次/分钟
  }

  /**
   * 检查动作是否安全
   */
  checkActionSafety(robotId: string, action: Action): SafetyCheckResult {
    // 检查频率限制
    if (!this.rateLimiter.check(robotId)) {
      return {
        safe: false,
        reason: '动作执行频率过高，请稍后再试',
      };
    }

    // 检查是否在白名单中
    if (!this.ALLOWED_ACTIONS.has(action.name)) {
      return {
        safe: false,
        reason: `动作 "${action.name}" 不在允许列表中`,
      };
    }

    // 检查参数范围
    const rule = this.SAFETY_RULES.find(r => r.action === action.name);
    if (rule) {
      // 检查步数、角度等参数
      const paramValue = action.parameters.steps || action.parameters.angle || action.parameters.value;
      
      if (paramValue !== undefined) {
        if (rule.maxValue && paramValue > rule.maxValue) {
          // 自动修正参数
          const sanitizedAction = { ...action };
          const paramKey = action.parameters.steps !== undefined ? 'steps' 
            : action.parameters.angle !== undefined ? 'angle' 
            : 'value';
          
          sanitizedAction.parameters = {
            ...action.parameters,
            [paramKey]: rule.maxValue,
          };

          return {
            safe: true,
            reason: `参数值超出安全范围，已自动调整为 ${rule.maxValue}`,
            sanitizedAction,
          };
        }

        if (rule.minValue && paramValue < rule.minValue) {
          return {
            safe: false,
            reason: `参数值低于最小值 ${rule.minValue}`,
          };
        }
      }
    }

    return { safe: true };
  }

  /**
   * 安全化动作参数
   */
  sanitizeAction(action: Action): Action {
    const checkResult = this.checkActionSafety('sanitize', action);
    return checkResult.sanitizedAction || action;
  }

  /**
   * 获取允许的动作列表
   */
  getAllowedActions(): string[] {
    return Array.from(this.ALLOWED_ACTIONS);
  }

  /**
   * 验证多个动作
   */
  validateActions(robotId: string, actions: Action[]): {
    validActions: Action[];
    rejectedActions: Array<{ action: Action; reason: string }>;
  } {
    const validActions: Action[] = [];
    const rejectedActions: Array<{ action: Action; reason: string }> = [];

    for (const action of actions) {
      const checkResult = this.checkActionSafety(robotId, action);
      if (checkResult.safe) {
        validActions.push(checkResult.sanitizedAction || action);
      } else {
        rejectedActions.push({
          action,
          reason: checkResult.reason || '未知错误',
        });
      }
    }

    return { validActions, rejectedActions };
  }
}

export default ActionController;