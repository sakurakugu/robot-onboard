from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
import time


class 监听管理器(ServiceListener):
    def __init__(self):
        self.robots = {}

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            self._process(info)

    def update_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            self._process(info)

    def _process(self, info):
        properties = {}
        if info.properties:
            for k, v in info.properties.items():
                if isinstance(k, bytes):
                    k = k.decode("utf-8", errors="ignore")
                if isinstance(v, bytes):
                    v = v.decode("utf-8", errors="ignore")
                properties[k] = v
        addresses = []
        if info.addresses:
            import socket
            for addr in info.addresses:
                try:
                    ip = socket.inet_ntoa(addr)
                    addresses.append(ip)
                except Exception:
                    pass
        ip = properties.get("ip") or (addresses[0] if addresses else "")
        port = int(properties.get("port", info.port or 8080))
        uuid = properties.get("uuid", "")
        if not uuid:
            return
        robot = {
            "uuid": uuid,
            "name": properties.get("name", f"机器狗-{uuid[:4]}"),
            "model": properties.get("model", "agibot-d1"),
            "version": properties.get("version", "0.0.0"),
            "ip": ip,
            "port": port,
            "service_name": info.name,
        }
        self.robots[uuid] = robot


def 发现机器人(timeout: float = 3.0):
    zc = Zeroconf()
    listener = 监听管理器()
    try:
        ServiceBrowser(zc, "_sparkrobot._tcp.local.", listener)
        time.sleep(timeout)
        return list(listener.robots.values())
    finally:
        zc.close()


def 扫描设备():
    print("\n" + "="*50)
    print("正在扫描设备...")
    print("="*50)
    try:
        robots = 发现机器人(3.0)
        if not robots:
            print("未发现设备")
        else:
            print(f"发现 {len(robots)} 台设备")
            print("-"*50)
            for i, r in enumerate(robots, 1):
                print(f"{i}. 名称: {r['name']}")
                print(f"   UUID: {r['uuid']}")
                print(f"   型号: {r['model']}  版本: {r['version']}")
                print(f"   地址: http://{r['ip']}:{r['port']}")
                print(f"   服务: {r['service_name']}")
                print("-"*50)
    except Exception as e:
        print(f"扫描失败: {e}")
    input("\n按回车键返回主菜单...")