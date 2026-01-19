import uuid6 # python3.11才自带uuid7，需要用第三方库
import logging
import datetime
from pathlib import Path
from typing import Union

# 生成uuid7
def generate_uuid() -> str:
    return str(uuid6.uuid7())
