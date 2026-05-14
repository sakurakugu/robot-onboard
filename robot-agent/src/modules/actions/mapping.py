import re
from typing import Any, Callable, Dict, Optional

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")


def 解析动作格式(text: str) -> Optional[Dict[str, Any]]:
    """
    解析动作格式字符串，提取动作名称和参数。

    :param text: 包含动作格式的字符串，例如 "{{action=forward,vx=0.2,vy=0,yaw_rate=0}}"。
    :return: 如果字符串符合动作格式，返回包含 "action" 和 "parameters" 键的字典；否则返回 None。
    """
    pattern = r"^\\{\\{action=([a-zA-Z_][a-zA-Z0-9_]*)((?:,[a-zA-Z_][a-zA-Z0-9_]*=[^,}]+)*)\\}\\}$"
    match = re.match(pattern, text)

    if not match:
        return None

    action = match.group(1)
    params_str = match.group(2)
    parameters: Dict[str, Any] = {}

    if params_str:
        param_pairs = params_str[1:].split(",")
        for pair in param_pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip()
                try:
                    if "." in value:
                        parameters[key] = float(value)
                    else:
                        parameters[key] = int(value)
                except ValueError:
                    parameters[key] = value

    return {"action": action, "parameters": parameters}


async def 处理文本响应(
    data: Dict[str, object],
    提交动作: Callable[[str, dict[str, object] | None], bool],
) -> None:
    """
    处理文本响应，解析动作格式并执行动作。

    :param data: 包含文本响应的字典，必须包含 "text" 键。
    :param 提交动作: 动作提交函数，用于转发统一动作命令。
    """
    text = data.get("text", "")
    logger.info(f"收到文本响应: {text}")

    action_data = 解析动作格式(text)
    if not action_data:
        return

    action = action_data["action"]
    parameters = action_data["parameters"]
    logger.info(f"检测到动作格式: 动作={action}, 参数={parameters}")

    try:
        accepted = 提交动作(action, parameters)
        if accepted:
            logger.info(f"动作 {action} 已提交到运行时")
        else:
            logger.warning(f"动作 {action} 提交失败")
    except Exception as e:
        logger.error(f"提交动作 {action} 时出错: {e}")


async def 处理动作指令(data: Dict[str, object], 提交动作: Callable[[str, dict[str, object] | None], bool]) -> None:
    """
    处理动作指令，将指令转发到运行时统一执行。

    :param data: 包含动作指令的字典，必须包含 "action" 和 "parameters" 键。
    :param 提交动作: 动作提交函数。
    """
    action = data.get("action", "")
    parameters = data.get("parameters", {})
    logger.info(f"收到动作指令: action={action}, parameters={parameters}")

    if not isinstance(action, str) or not action.strip():
        logger.warning("动作名称为空，跳过动作执行")
        return
    if not isinstance(parameters, dict):
        logger.warning("动作参数必须是对象，跳过动作执行")
        return
    try:
        accepted = 提交动作(action, parameters)
        logger.info(f"动作提交结果: {accepted}")
    except Exception as e:
        logger.error(f"提交动作失败: {e}")
