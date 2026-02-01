#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 配置
TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
BACKUPS_DIR = PROJECT_ROOT.parent / "backups"

# --- 动态配置区域 (脚本会自动修改这里) ---
ROBOT_IP = "192.168.0.85"
ROBOT_USER = "firefly"
# ---------------------------------------

# 颜色代码 (Windows 10+ 终端支持 ANSI 转义序列)
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    RED = '\033[0;31m'
    YELLOW = '\033[0;33m'
    NC = '\033[0m'

def print_info(msg: str):
    print(f"{Colors.BLUE}[信息]{Colors.NC} {msg}")

def print_success(msg: str):
    print(f"{Colors.GREEN}[成功]{Colors.NC} {msg}")

def print_error(msg: str):
    print(f"{Colors.RED}[错误]{Colors.NC} {msg}")

def print_warn(msg: str):
    print(f"{Colors.YELLOW}[警告]{Colors.NC} {msg}")

# --- 配置管理 ---

def update_script_config(key: str, value: str):
    """直接修改当前脚本文件中的配置变量"""
    script_path = Path(__file__)
    try:
        content = script_path.read_text(encoding='utf-8')
        
        # 使用正则替换变量值，保留引号
        # 匹配模式: key = "..." 或 key = '...'
        pattern = f'({key}\\s*=\\s*)["\'].*?["\']'
        replacement = f'\\1"{value}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            script_path.write_text(new_content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print_error(f"更新脚本配置失败: {e}")
        return False

# --- 功能函数 ---

def change_robot_ip():
    global ROBOT_IP
    
    print("\n------------------------------------------")
    print(f"当前机器狗 IP: {ROBOT_IP}")
    print("------------------------------------------")
    
    new_ip = input("请输入新的机器狗 IP 地址: ").strip()
    if not new_ip:
        return

    # 简单验证 IP 格式
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", new_ip):
        if update_script_config("ROBOT_IP", new_ip):
            ROBOT_IP = new_ip # 更新内存中的值
            print_success(f"机器狗 IP 已更新为: {new_ip}")
            print_info("配置已写入脚本文件")
        else:
            print_error("更新配置文件失败")
    else:
        print_error("无效的 IP 地址格式")
        time.sleep(1)
        change_robot_ip()

def get_ssh_config_path() -> Path:
    return Path.home() / ".ssh" / "config"

def get_robot_key_dir() -> Path:
    return Path.home() / ".ssh" / "robot"

def get_robot_key_path(robot_ip: str) -> Path:
    return get_robot_key_dir() / robot_ip

def upsert_ssh_config(robot_ip: str, robot_user: str, identity_file: Path):
    config_path = get_ssh_config_path()
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = ""
    else:
        content = config_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_block = [
        f"Host {robot_ip}",
        f"    HostName {robot_ip}",
        f"    User {robot_user}",
        f"    IdentityFile {identity_file}",
        "    IdentitiesOnly yes",
    ]
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Host "):
            hosts = line[5:].split()
            if robot_ip in hosts:
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("Host "):
                    j += 1
                lines = lines[:i] + new_block + lines[j:]
                replaced = True
                break
        i += 1
    if not replaced:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.extend(new_block)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def find_matching_key_path(key_dir: Path, key_bytes: bytes, exclude: Path) -> Optional[Path]:
    if not key_dir.exists():
        return None
    for path in key_dir.iterdir():
        if path == exclude or path.is_dir():
            continue
        if path.suffix in [".pub", ".tmp"]:
            continue
        try:
            if path.read_bytes() == key_bytes:
                return path
        except Exception:
            continue
    return None

def reconcile_local_key(temp_path: Path, final_path: Path) -> bool:
    if not temp_path.exists():
        return False
    key_dir = temp_path.parent
    key_bytes = temp_path.read_bytes()
    match_path = find_matching_key_path(key_dir, key_bytes, temp_path)
    if match_path:
        if match_path != final_path:
            if final_path.exists():
                final_path.unlink()
            match_path.rename(final_path)
        temp_path.unlink()
        return True
    if final_path.exists():
        if final_path.read_bytes() == key_bytes:
            temp_path.unlink()
            return True
        final_path.unlink()
    temp_path.rename(final_path)
    return True

def run_ssh_command(command: List[str], use_sshpass: bool):
    if use_sshpass:
        return subprocess.run(["sshpass", "-p", "firefly"] + command)
    return subprocess.run(command)

def ensure_remote_key_and_fetch(use_sshpass: bool) -> Optional[Path]:
    key_dir = get_robot_key_dir()
    key_dir.mkdir(parents=True, exist_ok=True)
    temp_key_path = key_dir / f"{ROBOT_IP}.tmp"
    remote_cmd = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        "if [ ! -f ~/.ssh/robot_dog ]; then ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/robot_dog; fi && "
        "if ! grep -q -F \"$(cat ~/.ssh/robot_dog.pub)\" ~/.ssh/authorized_keys 2>/dev/null; then "
        "cat ~/.ssh/robot_dog.pub >> ~/.ssh/authorized_keys; fi && "
        "chmod 600 ~/.ssh/authorized_keys"
    )
    ssh_cmd = ["ssh", f"{ROBOT_USER}@{ROBOT_IP}", "sh", "-lc", remote_cmd]
    scp_cmd = ["scp", f"{ROBOT_USER}@{ROBOT_IP}:~/.ssh/robot_dog", str(temp_key_path)]
    try:
        result = run_ssh_command(ssh_cmd, use_sshpass)
        if result.returncode != 0:
            return None
        result = run_ssh_command(scp_cmd, use_sshpass)
        if result.returncode != 0:
            return None
        final_key_path = get_robot_key_path(ROBOT_IP)
        if reconcile_local_key(temp_key_path, final_key_path):
            return final_key_path
    except FileNotFoundError:
        print_error("未找到 ssh 或 scp 命令，请确保已安装 OpenSSH Client")
    except Exception:
        pass
    return None

def try_ssh_with_key(key_path: Path) -> bool:
    if not key_path.exists():
        return False
    try:
        result = subprocess.run([
            "ssh",
            "-i",
            str(key_path),
            "-o",
            "IdentitiesOnly=yes",
            f"{ROBOT_USER}@{ROBOT_IP}",
        ])
        return result.returncode == 0
    except FileNotFoundError:
        print_error("未找到 ssh 命令，请确保已安装 OpenSSH Client")
    return False

def connect_robot():
    print_info(f"正在连接机器狗 ({ROBOT_USER}@{ROBOT_IP})...")
    key_path = get_robot_key_path(ROBOT_IP)
    if key_path.exists() and try_ssh_with_key(key_path):
        return
    use_sshpass = sys.platform != "win32" and shutil.which("sshpass")
    fetched_key_path = ensure_remote_key_and_fetch(use_sshpass)
    if fetched_key_path:
        upsert_ssh_config(ROBOT_IP, ROBOT_USER, fetched_key_path)
        if try_ssh_with_key(fetched_key_path):
            return
    try:
        subprocess.run(["ssh", f"{ROBOT_USER}@{ROBOT_IP}"])
    except FileNotFoundError:
        print_error("未找到 ssh 命令，请确保已安装 OpenSSH Client")

def get_iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

def backup_files(source_dir: Path, dest_dir: Path, ignore_patterns: List[str] = None):
    """使用 shutil.copytree 进行备份"""
    try:
        if ignore_patterns:
            shutil.copytree(source_dir, dest_dir, ignore=shutil.ignore_patterns(*ignore_patterns))
        else:
            shutil.copytree(source_dir, dest_dir)
        print_success(f"备份完成: {dest_dir}")
    except Exception as e:
        print_error(f"备份失败: {e}")

def backup_git_files(source_dir: Path, dest_dir: Path):
    """仅备份 git 管理的文件"""
    try:
        # 获取 git 文件列表
        result = subprocess.run(
            ["git", "ls-files"], 
            cwd=source_dir, 
            capture_output=True, 
            text=True, 
            check=True
        )
        files = result.stdout.splitlines()
        
        print_info(f"检测到 {len(files)} 个受版本控制的文件")
        
        for rel_path in files:
            src_file = source_dir / rel_path
            dst_file = dest_dir / rel_path
            
            if src_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
        
        print_success(f"Git 文件备份完成: {dest_dir}")
        
    except subprocess.CalledProcessError:
        print_warn("获取 Git 文件列表失败，可能不是 Git 仓库。回退到完整备份。")
        backup_files(source_dir, dest_dir)
    except Exception as e:
        print_error(f"备份失败: {e}")

def backup_menu():
    root_name = PROJECT_ROOT.name
    
    print("\n------------------------------------------")
    print("备份选项:")
    print("  1) 备份全部")
    print("  2) 排除常见目录 (node_modules, dist, venv, etc.)")
    print("  3) 按 .gitignore 排除 (仅备份 Git 追踪文件)")
    print("------------------------------------------")
    
    choice = input("请选择备份类型: ").strip()
    
    if choice not in ["1", "2", "3"]:
        print_error("无效选项")
        return

    name = input(f"备份目录名(回车使用默认: {root_name}): ").strip() or root_name
    timestamp = get_iso_now()
    dest_path = BACKUPS_DIR / name / timestamp
    
    print_info(f"目标路径: {dest_path}")
    
    if choice == "1":
        backup_files(PROJECT_ROOT, dest_path)
    elif choice == "2":
        ignores = [
            "node_modules", "build", "__pycache__", "dist", 
            ".venv", "venv", ".pytest_cache", ".git", ".idea", ".vscode"
        ]
        backup_files(PROJECT_ROOT, dest_path, ignores)
    elif choice == "3":
        backup_git_files(PROJECT_ROOT, dest_path)

def fix_git_refs():
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        print_error("未检测到 .git 目录")
        return

    # 修复 Windows 可能出现的 Zone.Identifier 文件
    bad_ref = git_dir / "refs" / "heads" / "main:Zone.Identifier"
    if bad_ref.exists():
        try:
            os.remove(bad_ref)
            print_success("已删除 refs/heads/main:Zone.Identifier")
        except Exception as e:
            print_error(f"删除文件失败: {e}")

    packed_refs = git_dir / "packed-refs"
    if packed_refs.exists():
        try:
            content = packed_refs.read_text(encoding="utf-8")
            if "main:Zone.Identifier" in content:
                new_content = "\n".join([line for line in content.splitlines() if "main:Zone.Identifier" not in line])
                packed_refs.write_text(new_content, encoding="utf-8")
                print_success("已清理 packed-refs 中的异常引用")
        except Exception as e:
            print_error(f"处理 packed-refs 失败: {e}")
            
    try:
        subprocess.run(["git", "fetch", "--prune", "--tags", "origin"], cwd=PROJECT_ROOT, check=False)
        print_success("已执行 git fetch --prune")
    except Exception:
        pass

def git_amend_commit():
    if not (PROJECT_ROOT / ".git").exists():
        print_error("不是 Git 仓库")
        return
        
    try:
        # 获取当前分支
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=PROJECT_ROOT, text=True).strip()
        print_info(f"当前分支: {branch}")
        
        input("按回车开始修改（Git 默认编辑器）: ")
        subprocess.run(["git", "commit", "--amend"], cwd=PROJECT_ROOT)
        print_success("已更新上次提交日志")
        
        choice = input("是否需要安全推送 (git push --force-with-lease)? (y/N): ").strip().lower()
        if choice == "y":
            ret = subprocess.run(["git", "push", "--force-with-lease"], cwd=PROJECT_ROOT)
            if ret.returncode == 0:
                print_success("已安全推送更新")
            else:
                print_error("推送失败")
                
    except Exception as e:
        print_error(f"操作失败: {e}")

def fix_common_errors():
    print("\n------------------------------------------")
    print("修复常见错误:")
    print("  1) 修复 Git refs/heads/main:Zone.Identifier")
    print("  2) 修改 Git 上次提交日志 (amend)")
    print("  0) 返回")
    print("------------------------------------------")
    
    choice = input("请选择修复项: ").strip()
    if choice == "1":
        fix_git_refs()
    elif choice == "2":
        git_amend_commit()
    elif choice == "0":
        return
    else:
        print_error("无效选项")

def show_menu():
    print("\n==========================================")
    print("    机器狗项目 - 常用命令 (Python版)")
    print("==========================================")
    print(f"  1) SSH 连接机器狗 ({ROBOT_USER}@{ROBOT_IP})")
    print("  2) 备份当前项目文件夹")
    print("  3) 修复常见错误")
    print("  4) 设置 (修改 IP)")
    print("  0) 退出")
    print("")
    print("==========================================")

def main():
    # 确保能够显示颜色
    os.system("") 
    
    while True:
        try:
            show_menu()
            choice = input("请输入选项编号: ").strip()
            
            if choice == "1":
                connect_robot()
            elif choice == "2":
                backup_menu()
            elif choice == "3":
                fix_common_errors()
            elif choice == "4":
                change_robot_ip()
            elif choice == "0":
                print_success("退出脚本")
                sys.exit(0)
            else:
                print_error("无效选项，请重新选择")
            
            input("\n按回车键继续...")
            
        except KeyboardInterrupt:
            print("\n")
            print_success("退出脚本")
            sys.exit(0)

if __name__ == "__main__":
    main()
