import subprocess
from typing import TypedDict

# TODO：抽象出WiFiManager类

class WiFi信息(TypedDict):
    ssid: str
    signal: str
    channel: str
    security: str
    in_use: bool

def 连接WiFi(ssid: str, password: str) -> None:
    connect_cmd = f"sudo nmcli device wifi connect '{ssid}' password '{password}' ifname wlan0"
    subprocess.run(connect_cmd, shell=True, check=True, capture_output=True, text=True)

    subprocess.run("sudo systemctl stop networkmanager-cleanup.service", shell=True, capture_output=True, text=True)
    subprocess.run("sudo systemctl disable networkmanager-cleanup.service", shell=True, capture_output=True, text=True)

    auto_connect_cmd = f"sudo nmcli connection modify '{ssid}' connection.autoconnect yes"
    subprocess.run(auto_connect_cmd, shell=True, capture_output=True, text=True)


def 扫描WiFi() -> list[WiFi信息]:
    scan_cmd = "sudo nmcli -t -f IN-USE,SSID,CHAN,SIGNAL,SECURITY device wifi list"
    result = subprocess.run(scan_cmd, shell=True, check=True, capture_output=True, text=True)

    wifi_list: list[WiFi信息] = []
    lines = result.stdout.strip().split("\n")

    for line in lines:
        if not line:
            continue

        parts = []
        current = ""
        escaped = False
        for char in line:
            if escaped:
                current += char
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == ":":
                parts.append(current)
                current = ""
            else:
                current += char
        parts.append(current)

        if len(parts) >= 5:
            in_use = parts[0] == "*"
            ssid = parts[1]
            channel = parts[2]
            signal = parts[3]
            security = parts[4]

            if not ssid:
                continue

            wifi_list.append(
                WiFi信息(
                    ssid=ssid,
                    signal=signal,
                    channel=channel,
                    security=security,
                    in_use=in_use,
                )
            )

    wifi_list.sort(key=lambda x: (not x["in_use"], -int(x["signal"]) if x["signal"].isdigit() else 0))

    return wifi_list
