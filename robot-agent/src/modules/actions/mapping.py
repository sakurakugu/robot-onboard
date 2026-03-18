import re
from typing import Any, Dict, Optional

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


async def 处理文本响应(data: Dict[str, Any], action_executor, executor) -> None:
    """
    处理文本响应，解析动作格式并执行动作。

    :param data: 包含文本响应的字典，必须包含 "text" 键。
    :param action_executor: 动作执行器函数，用于执行具体的动作。
    :param executor: 线程池执行器，用于在独立线程中执行动作执行器。
    """
    text = data.get("text", "")
    logger.info(f"收到文本响应: {text}")

    action_data = 解析动作格式(text)
    if not action_data:
        return

    action = action_data["action"]
    parameters = action_data["parameters"]
    logger.info(f"检测到动作格式: 动作={action}, 参数={parameters}")

    if action_executor:
        try:
            result = action_executor(action, parameters)
            if result:
                logger.info(f"动作 {action} 执行成功")
            else:
                logger.warning(f"动作 {action} 执行失败或不支持")
        except Exception as e:
            logger.error(f"执行动作 {action} 时出错: {e}")
    else:
        logger.warning("未设置动作执行器，无法执行动作")


async def 处理动作指令(data: Dict[str, Any], action_executor, executor) -> None:
    """
    处理动作指令，将指令发送给动作执行器执行。

    :param data: 包含动作指令的字典，必须包含 "action" 和 "parameters" 键。
    :param action_executor: 动作执行器函数，用于执行具体的动作。
    :param executor: 线程池执行器，用于在独立线程中执行动作执行器。
    """
    action = data.get("action", "")
    parameters = data.get("parameters", {})
    logger.info(f"收到动作指令: action={action}, parameters={parameters}")

    if action_executor:
        try:
            result = action_executor(action, parameters)
            logger.info(f"动作执行结果: {result}")
        except Exception as e:
            logger.error(f"执行动作失败: {e}")
    else:
        logger.warning("未设置动作执行器，跳过动作执行")
