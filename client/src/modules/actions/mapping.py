import asyncio
import re
from typing import Any, Dict, Optional


def parse_action_format(text: str) -> Optional[Dict[str, Any]]:
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


async def handle_text_response(data: Dict[str, Any], logger, action_executor, executor) -> None:
    text = data.get("text", "")
    logger.info(f"收到文本响应: {text}")

    action_data = parse_action_format(text)
    if not action_data:
        return

    action = action_data["action"]
    parameters = action_data["parameters"]
    logger.info(f"检测到动作格式: action={action}, parameters={parameters}")

    if action_executor:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, action_executor, action, parameters)
            if result:
                logger.info(f"动作 {action} 执行成功")
            else:
                logger.warning(f"动作 {action} 执行失败或不支持")
        except Exception as e:
            logger.error(f"执行动作 {action} 时出错: {e}")
    else:
        logger.warning("未设置动作执行器，无法执行动作")


async def handle_action_command(data: Dict[str, Any], logger, action_executor, executor) -> None:
    action = data.get("action", "")
    parameters = data.get("parameters", {})
    logger.info(f"收到动作指令: action={action}, parameters={parameters}")

    if action_executor:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, action_executor, action, parameters)
            logger.info(f"动作执行结果: {result}")
        except Exception as e:
            logger.error(f"执行动作失败: {e}")
    else:
        logger.warning("未设置动作执行器，跳过动作执行")
