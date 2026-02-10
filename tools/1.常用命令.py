#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import shutil
import subprocess
import configparser
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 配置
TOOLS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TOOLS_DIR / "scripts"
PROJECT_ROOT = TOOLS_DIR.parent
BACKUPS_DIR = PROJECT_ROOT.parent / "backups"
CONFIG_FILE = SCRIPTS_DIR / "config" / "config.ini"

ROBOT_USER = "firefly"

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

# --- 配置文件管理 ---

def 确保配置文件存在():
    """确保配置文件存在"""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config['robots'] = {'robot1': '192.168.1.106'}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        print_info(f"已创建配置文件: {CONFIG_FILE}")

def load_robots() -> Dict[str, str]:
    """从配置文件加载机器狗列表"""
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')

    if 'robots' not in config:
        return {}

    return dict(config['robots'])

def 保存机器狗列表(robots: Dict[str, str]):
    """保存机器狗列表到配置文件"""
    确保配置文件存在()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')

    config['robots'] = robots

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)

# --- 功能函数 ---

def 机器狗列表菜单():
    """机器狗列表菜单"""
    while True:
        robots = load_robots()

        print("\n------------------------------------------")
        print("    机器狗列表")
        print("------------------------------------------")

        if not robots:
            print("  (暂无机器狗，请先添加)")
        else:
            for idx, (name, ip) in enumerate(robots.items(), 1):
                print(f"  {idx}) {name} ({ip})")

        print("------------------------------------------")
        print("  a) 添加机器狗")
        print("  0) 返回主菜单")
        print("------------------------------------------")

        choice = input("请选择要连接的机器狗 (输入编号) 或操作: ").strip().lower()

        if choice == "0":
            return
        elif choice == "a":
            添加机器狗()
        elif choice.isdigit():
            idx = int(choice)
            robot_list = list(robots.items())
            if 1 <= idx <= len(robot_list):
                name, ip = robot_list[idx - 1]
                连接机器狗(name, ip)
            else:
                print_error("无效的编号")
        else:
            print_error("无效选项")

def 添加机器狗():
    """添加新机器狗"""
    robots = load_robots()

    print("\n------------------------------------------")
    print("添加新机器狗")
    print("------------------------------------------")

    name = input("请输入机器狗名称 (如 robot1): ").strip()
    if not name:
        print_error("名称不能为空")
        return

    if name in robots:
        print_error(f"名称 '{name}' 已存在")
        return

    ip = input("请输入机器狗 IP 地址: ").strip()
    if not ip:
        print_error("IP 地址不能为空")
        return

    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        print_error("无效的 IP 地址格式")
        return

    robots[name] = ip
    保存机器狗列表(robots)
    print_success(f"已添加机器狗: {name} ({ip})")

def 运行ssh命令(command: List[str], use_sshpass: bool):
    """运行 SSH 命令"""
    if use_sshpass:
        return subprocess.run(["sshpass", "-p", "firefly"] + command)
    return subprocess.run(command)

def 连接机器狗(name: str, ip: str):
    """连接机器狗"""
    print_info(f"正在连接机器狗 {name} ({ROBOT_USER}@{ip})...")
    use_sshpass = sys.platform != "win32" and shutil.which("sshpass")
    ssh_cmd = ["ssh", f"{ROBOT_USER}@{ip}"]
    try:
        运行ssh命令(ssh_cmd, use_sshpass)
    except FileNotFoundError:
        print_error("未找到 ssh 命令，请确保已安装 OpenSSH Client")

def 获取当前时间戳() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

def 备份文件(source_dir: Path, dest_dir: Path, ignore_patterns: List[str] = None):
    """使用 shutil.copytree 进行备份"""
    try:
        if ignore_patterns:
            shutil.copytree(source_dir, dest_dir, ignore=shutil.ignore_patterns(*ignore_patterns))
        else:
            shutil.copytree(source_dir, dest_dir)
        print_success(f"备份完成: {dest_dir}")
    except Exception as e:
        print_error(f"备份失败: {e}")

def 备份git文件(source_dir: Path, dest_dir: Path):
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
        备份文件(source_dir, dest_dir)
    except Exception as e:
        print_error(f"备份失败: {e}")

def 备份菜单():
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
    timestamp = 获取当前时间戳()
    dest_path = BACKUPS_DIR / name / timestamp

    print_info(f"目标路径: {dest_path}")

    if choice == "1":
        备份文件(PROJECT_ROOT, dest_path)
    elif choice == "2":
        ignores = [
            "node_modules", "build", "__pycache__", "dist",
            ".venv", "venv", ".pytest_cache", ".git", ".idea", ".vscode"
        ]
        备份文件(PROJECT_ROOT, dest_path, ignores)
    elif choice == "3":
        备份git文件(PROJECT_ROOT, dest_path)

def 修复git_refs():
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

def 修改git上次提交日志():
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

def 修复常见错误():
    print("\n------------------------------------------")
    print("修复常见错误:")
    print("  1) 修复 Git refs/heads/main:Zone.Identifier")
    print("  2) 修改 Git 上次提交日志 (amend)")
    print("  3) 修复 Gradle 缺失的 Eclipse Buildship 配置")
    print("  0) 返回")
    print("------------------------------------------")

    choice = input("请选择修复项: ").strip()
    if choice == "1":
        修复git_refs()
    elif choice == "2":
        修改git上次提交日志()
    elif choice == "3":
        修复gradle_buildship_configs()
    elif choice == "0":
        return
    else:
        print_error("无效选项")

def 修复gradle_buildship_configs():
    """修复 Gradle 项目缺失的 Eclipse Buildship 配置文件"""
    print("\n------------------------------------------")
    print("修复 Gradle Buildship 配置:")
    print("  1) 自动修复 React Native Gradle Plugin")
    print("  2) 扫描整个工作区")
    print("  3) 指定目录")
    print("  4) 预览模式（不实际创建文件）")
    print("  0) 返回")
    print("------------------------------------------")

    choice = input("请选择: ").strip()
    script_path = SCRIPTS_DIR / "fix" / "fix_gradle_settings.py"

    if choice == "1":
        print_info("正在修复 React Native Gradle Plugin...")
        result = subprocess.run([sys.executable, str(script_path)],
                              cwd=PROJECT_ROOT,
                              capture_output=False)
        if result.returncode == 0:
            print_success("修复完成！")
        else:
            print_error("修复失败")

    elif choice == "2":
        print_info("正在扫描整个工作区...")
        result = subprocess.run([sys.executable, str(script_path), "--scan-all"],
                              cwd=PROJECT_ROOT,
                              capture_output=False)
        if result.returncode == 0:
            print_success("扫描完成！")
        else:
            print_error("扫描失败")

    elif choice == "3":
        target_dir = input("请输入目录路径: ").strip()
        if target_dir:
            print_info(f"正在修复目录: {target_dir}")
            result = subprocess.run([sys.executable, str(script_path), "--path", target_dir],
                                  cwd=PROJECT_ROOT,
                                  capture_output=False)
            if result.returncode == 0:
                print_success("修复完成！")
            else:
                print_error("修复失败")
        else:
            print_error("目录路径不能为空")

    elif choice == "4":
        print_info("预览模式 - 不会实际创建文件")
        result = subprocess.run([sys.executable, str(script_path), "--dry-run"],
                              cwd=PROJECT_ROOT,
                              capture_output=False)

    elif choice == "0":
        return
    else:
        print_error("无效选项")

def 设置菜单():
    """设置菜单 - 管理机器狗配置"""
    while True:
        robots = load_robots()

        print("\n------------------------------------------")
        print("    设置 - 机器狗管理")
        print("------------------------------------------")

        if not robots:
            print("  (暂无机器狗)")
        else:
            for idx, (name, ip) in enumerate(robots.items(), 1):
                print(f"  {idx}) {name} = {ip}")

        print("------------------------------------------")
        print("  a) 添加机器狗")
        print("  e) 编辑机器狗 (修改名称或IP)")
        print("  d) 删除机器狗")
        print("  0) 返回主菜单")
        print("------------------------------------------")

        choice = input("请选择操作: ").strip().lower()

        if choice == "0":
            return
        elif choice == "a":
            添加机器狗()
        elif choice == "e":
            编辑机器狗()
        elif choice == "d":
            删除机器狗()
        else:
            print_error("无效选项")

def 编辑机器狗():
    """编辑机器狗配置"""
    robots = load_robots()

    if not robots:
        print_error("暂无机器狗可编辑")
        return

    print("\n------------------------------------------")
    print("选择要编辑的机器狗:")
    print("------------------------------------------")

    for idx, (name, ip) in enumerate(robots.items(), 1):
        print(f"  {idx}) {name} = {ip}")

    print("------------------------------------------")

    choice = input("请输入编号: ").strip()

    if not choice.isdigit():
        print_error("无效输入")
        return

    idx = int(choice)
    robot_list = list(robots.items())

    if not (1 <= idx <= len(robot_list)):
        print_error("无效的编号")
        return

    old_name, old_ip = robot_list[idx - 1]

    print(f"\n当前: {old_name} = {old_ip}")
    print("------------------------------------------")
    print("  1) 修改名称")
    print("  2) 修改 IP")
    print("  3) 同时修改名称和 IP")
    print("  0) 取消")
    print("------------------------------------------")

    edit_choice = input("请选择: ").strip()

    if edit_choice == "0":
        return
    elif edit_choice == "1":
        new_name = input(f"请输入新名称 (当前: {old_name}): ").strip()
        if not new_name:
            print_error("名称不能为空")
            return
        if new_name != old_name and new_name in robots:
            print_error(f"名称 '{new_name}' 已存在")
            return
        # 删除旧键，添加新键
        del robots[old_name]
        robots[new_name] = old_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' 改名为 '{new_name}'")

    elif edit_choice == "2":
        new_ip = input(f"请输入新 IP (当前: {old_ip}): ").strip()
        if not new_ip:
            print_error("IP 不能为空")
            return
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", new_ip):
            print_error("无效的 IP 地址格式")
            return
        robots[old_name] = new_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' 的 IP 修改为 '{new_ip}'")

    elif edit_choice == "3":
        new_name = input(f"请输入新名称 (当前: {old_name}): ").strip()
        if not new_name:
            print_error("名称不能为空")
            return
        if new_name != old_name and new_name in robots:
            print_error(f"名称 '{new_name}' 已存在")
            return

        new_ip = input(f"请输入新 IP (当前: {old_ip}): ").strip()
        if not new_ip:
            print_error("IP 不能为空")
            return
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", new_ip):
            print_error("无效的 IP 地址格式")
            return

        del robots[old_name]
        robots[new_name] = new_ip
        保存机器狗列表(robots)
        print_success(f"已将 '{old_name}' ({old_ip}) 修改为 '{new_name}' ({new_ip})")
    else:
        print_error("无效选项")

def 删除机器狗():
    """删除机器狗"""
    robots = load_robots()

    if not robots:
        print_error("暂无机器狗可删除")
        return

    print("\n------------------------------------------")
    print("选择要删除的机器狗:")
    print("------------------------------------------")

    for idx, (name, ip) in enumerate(robots.items(), 1):
        print(f"  {idx}) {name} = {ip}")

    print("------------------------------------------")

    choice = input("请输入编号: ").strip()

    if not choice.isdigit():
        print_error("无效输入")
        return

    idx = int(choice)
    robot_list = list(robots.items())

    if not (1 <= idx <= len(robot_list)):
        print_error("无效的编号")
        return

    name, ip = robot_list[idx - 1]

    confirm = input(f"确认删除 '{name}' ({ip})? (y/N): ").strip().lower()
    if confirm == "y":
        del robots[name]
        保存机器狗列表(robots)
        print_success(f"已删除机器狗: {name}")

def 显示菜单():
    robots = load_robots()
    robot_count = len(robots)

    print("\n==========================================")
    print("    机器狗项目 - 常用命令 (Python版)")
    print("==========================================")
    print(f"  1) SSH 连接机器狗 (已保存 {robot_count} 个)")
    print("  2) 备份当前项目文件夹")
    print("  3) 修复常见错误")
    print("  4) 设置 (管理机器狗)")
    print("  0) 退出")
    print("")
    print("==========================================")

def main():
    # 确保能够显示颜色
    os.system("")

    # 确保配置文件存在
    确保配置文件存在()

    while True:
        try:
            显示菜单()
            choice = input("请输入选项编号: ").strip()

            if choice == "1":
                机器狗列表菜单()
            elif choice == "2":
                备份菜单()
            elif choice == "3":
                修复常见错误()
            elif choice == "4":
                设置菜单()
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
