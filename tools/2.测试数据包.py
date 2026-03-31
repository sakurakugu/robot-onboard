import argparse
import importlib
import json
import socket
import struct
import threading
import time
from pathlib import Path

# ── 初始化 colorama ─────────────────────────────────────────────────────────────
colorama = importlib.import_module("colorama")
init = colorama.init
Fore = colorama.Fore
init(autoreset=True)

DOG_IP       = "192.168.1.108"
SEND_PORT    = 8081
LISTEN_PORT  = 8080
DATA_PACKAGE = json.dumps({"type": "heartbeat", "heartbeat": 1}).encode()
# DATA_PACKAGE = json.dumps({"type": "cmd", "cmd": 4}).encode()


def _read_pcap_packets(pcap_path: Path):
    with pcap_path.open("rb") as f:
        header = f.read(24)
        if len(header) < 24:
            raise ValueError("pcap 文件头长度不足")
        magic_bytes = header[:4]
        if magic_bytes in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            endian = ">"
        elif magic_bytes in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            endian = "<"
        elif magic_bytes == b"\x0a\x0d\x0d\x0a":
            raise ValueError("暂不支持 pcapng 格式")
        else:
            raise ValueError("未知 pcap 魔数")

        _, _, _, _, _, network = struct.unpack(f"{endian}HHIIII", header[4:24])

        while True:
            pkt_header = f.read(16)
            if len(pkt_header) < 16:
                break
            _, _, incl_len, _ = struct.unpack(f"{endian}IIII", pkt_header)
            if incl_len <= 0:
                continue
            data = f.read(incl_len)
            if len(data) < incl_len:
                break
            yield network, data


def _extract_ipv4_udp(packet: bytes, offset: int) -> bytes | None:
    if len(packet) < offset + 20:
        return None
    ver_ihl = packet[offset]
    version = ver_ihl >> 4
    if version != 4:
        return None
    ihl = (ver_ihl & 0x0F) * 4
    if len(packet) < offset + ihl + 8:
        return None
    protocol = packet[offset + 9]
    if protocol != 17:
        return None
    udp_offset = offset + ihl
    payload_offset = udp_offset + 8
    if payload_offset > len(packet):
        return None
    return packet[payload_offset:]


def _extract_udp_payload(packet: bytes, linktype: int) -> bytes | None:
    if linktype == 1:
        if len(packet) < 14:
            return None
        eth_type = struct.unpack("!H", packet[12:14])[0]
        offset = 14
        if eth_type == 0x8100:
            if len(packet) < 18:
                return None
            eth_type = struct.unpack("!H", packet[16:18])[0]
            offset = 18
        if eth_type != 0x0800:
            return None
        return _extract_ipv4_udp(packet, offset)
    if linktype == 113:
        if len(packet) < 16:
            return None
        eth_type = struct.unpack("!H", packet[14:16])[0]
        if eth_type != 0x0800:
            return None
        return _extract_ipv4_udp(packet, 16)
    if linktype == 101:
        return _extract_ipv4_udp(packet, 0)
    if linktype == 0:
        if len(packet) < 4:
            return None
        family = struct.unpack("<I", packet[:4])[0]
        if family != 2:
            return None
        return _extract_ipv4_udp(packet, 4)
    return None


def export_pcap_json(pcap_path: Path, output_path: Path) -> int:
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    decoder = json.JSONDecoder()
    with output_path.open("w", encoding="utf-8") as f:
        for linktype, packet in _read_pcap_packets(pcap_path):
            payload = _extract_udp_payload(packet, linktype)
            if not payload:
                continue
            text = payload.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            start = text.find("{")
            if start == -1:
                continue
            try:
                obj, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            f.write(json.dumps(obj, ensure_ascii=False))
            f.write("\n")
            count += 1
    return count


def receiver(sock: socket.socket, stop_event: threading.Event, max_packets: int):
    received = 0
    type_counter: dict[str, int] = {}

    print(Fore.CYAN + f"\n[RX] 监听 UDP :{LISTEN_PORT} …\n")
    while not stop_event.is_set():
        try:
            sock.settimeout(1.0)
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        received += 1
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
            pkt_type = obj.get("type", "<unknown>")
            type_counter[pkt_type] = type_counter.get(pkt_type, 0) + 1

            if type_counter[pkt_type] <= 3:
                print(Fore.GREEN + f"[RX #{received:04d}] {addr}  type={pkt_type}")
                pretty = json.dumps(obj, ensure_ascii=False, indent=2)
                if len(pretty) > 600:
                    pretty = pretty[:600] + "\n  … (已截断)"
                print(Fore.GREEN + pretty + "\n")
        except json.JSONDecodeError:
            print(Fore.RED + f"[RX #{received:04d}] {addr}  <非 JSON，{len(data)} 字节>")
            print(Fore.RED + str(data[:120]) + "\n")

        if max_packets > 0 and received >= max_packets:
            stop_event.set()
            break

    print(Fore.CYAN + "\n── 接收统计 ──────────────────────────────")
    print(Fore.CYAN + f"总计收到 {received} 个包")
    for t, c in sorted(type_counter.items(), key=lambda x: -x[1]):
        print(Fore.CYAN + f"  {t:30s}: {c}")
    print(Fore.CYAN + "──────────────────────────────────────────")


def main():
    print("\033]0;测试数据包\007")
    parser = argparse.ArgumentParser(description="机器狗数据包测试")
    parser.add_argument("--pcap", type=str, help="pcap 文件路径，传入后导出 JSONL")
    parser.add_argument("--out", type=str, help="导出 JSONL 文件路径")
    parser.add_argument("--dog-ip",   default=DOG_IP,  help="机器狗 IP")
    parser.add_argument("--count",    type=int, default=1,   help="发送数据包次数（0=无限）")
    parser.add_argument("--interval", type=float, default=0.2, help="发送间隔(秒)")
    parser.add_argument("--rx-max",   type=int, default=0,
                        help="最多接收多少包后停止（0=跟随发送完成后再等 3 秒）")
    args = parser.parse_args()

    if args.pcap:
        pcap_path = Path(args.pcap)
        output_path = Path(args.out) if args.out else pcap_path.with_suffix(".jsonl")
        try:
            count = export_pcap_json(pcap_path, output_path)
        except Exception as e:
            print(Fore.RED + f"[ERROR] 导出失败: {e}")
            return
        print(Fore.CYAN + f"[DONE] 已导出 {count} 行 JSON 到 {output_path}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("", LISTEN_PORT))
    except OSError as e:
        print(Fore.RED + f"[ERROR] 无法绑定 UDP :{LISTEN_PORT}  ->  {e}")
        print(Fore.RED + "        请检查端口是否被占用，或用管理员权限运行。")
        return

    stop_event = threading.Event()
    rx_thread = threading.Thread(
        target=receiver, args=(sock, stop_event, args.rx_max), daemon=True
    )
    rx_thread.start()

    total = args.count if args.count > 0 else float("inf")
    sent = 0
    print(Fore.MAGENTA + f"[TX] 发送数据包  ->  {args.dog_ip}:{SEND_PORT}")
    print(Fore.MAGENTA + f"     payload = {DATA_PACKAGE.decode()}")
    print(Fore.MAGENTA + f"     count={args.count}  interval={args.interval}s\n")

    try:
        while sent < total:
            sock.sendto(DATA_PACKAGE, (args.dog_ip, SEND_PORT))
            sent += 1
            print(Fore.YELLOW + f"[TX #{sent:04d}] 发送数据包")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(Fore.RED + "\n[TX] 用户中断发送")

    wait = 3.0
    print(Fore.MAGENTA + f"\n[TX] 发送完毕，等待 {wait}s 接收剩余回包 …")
    time.sleep(wait)
    stop_event.set()
    rx_thread.join(timeout=2)
    sock.close()
    print(Fore.CYAN + "[DONE]")


if __name__ == "__main__":
    main()
