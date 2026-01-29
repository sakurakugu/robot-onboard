#!/usr/bin/env python3
"""
SSH连接辅助工具 - 自动处理机器狗的SSH连接和文件传输
"""
import sys
import json
import paramiko
import os

# 默认SSH配置
SSH_USER = 'firefly'
SSH_PASSWORD = 'firefly'
SSH_PORT = 22

def test_ssh_connection(robot_ip):
    """测试SSH连接"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=robot_ip,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=5,
            look_for_keys=False,
            allow_agent=False
        )
        client.close()
        return True
    except Exception as e:
        print(f"SSH连接失败: {str(e)}", file=sys.stderr)
        return False

def execute_remote_command(robot_ip, command):
    """在远程机器上执行命令并返回输出"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=robot_ip,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        exit_code = stdout.channel.recv_exit_status()
        
        client.close()
        
        if exit_code != 0 and error:
            raise Exception(error)
        
        return output
    except Exception as e:
        raise Exception(f"执行远程命令失败: {str(e)}")

def write_remote_file(robot_ip, remote_path, content):
    """写入远程文件"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=robot_ip,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        
        sftp = client.open_sftp()
        
        # 确保目录存在
        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                # 递归创建目录
                parts = remote_dir.split('/')
                current = ''
                for part in parts:
                    if not part:
                        continue
                    current = current + '/' + part if current else '/' + part
                    try:
                        sftp.stat(current)
                    except FileNotFoundError:
                        sftp.mkdir(current)
        
        # 写入文件
        with sftp.file(remote_path, 'w') as f:
            f.write(content)
        
        sftp.close()
        client.close()
        return True
    except Exception as e:
        raise Exception(f"写入远程文件失败: {str(e)}")

def copy_directory(robot_ip, local_path, remote_path):
    """递归复制本地目录到远程机器"""
    try:
        # 验证本地路径
        if not os.path.exists(local_path):
            raise Exception(f"本地路径不存在: {local_path}")
        if not os.path.isdir(local_path):
            raise Exception(f"本地路径不是目录: {local_path}")
        
        # 转换为绝对路径
        local_path = os.path.abspath(local_path)
        print(f"[INFO] 开始复制: {local_path} -> {robot_ip}:{remote_path}", file=sys.stderr)
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=robot_ip,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )
        
        print(f"[INFO] SSH连接成功: {robot_ip}", file=sys.stderr)
        
        sftp = client.open_sftp()
        
        def mkdir_p(path):
            """递归创建远程目录"""
            try:
                print(f"[DEBUG] 检查远程目录: {path}", file=sys.stderr)
                sftp.stat(path)
                print(f"[DEBUG] 目录已存在: {path}", file=sys.stderr)
            except FileNotFoundError:
                parent = os.path.dirname(path)
                if parent and parent != '/' and parent != path:
                    mkdir_p(parent)
                print(f"[DEBUG] 创建目录: {path}", file=sys.stderr)
                sftp.mkdir(path)
            except Exception as e:
                print(f"[ERROR] mkdir_p异常 {path}: {e}", file=sys.stderr)
                raise
        
        def upload_recursive(local_dir, remote_dir):
            """递归上传目录"""
            mkdir_p(remote_dir)
            
            try:
                items = os.listdir(local_dir)
            except PermissionError as e:
                print(f"[ERROR] 无法读取目录 {local_dir}: {e}", file=sys.stderr)
                raise
            
            for item in items:
                local_item = os.path.join(local_dir, item)
                remote_item = os.path.join(remote_dir, item).replace('\\', '/')
                
                # 跳过特殊文件
                if item.startswith('.'):
                    print(f"[SKIP] 跳过隐藏文件: {item}", file=sys.stderr)
                    continue
                
                try:
                    if os.path.isfile(local_item):
                        print(f"[INFO] 上传文件: {local_item} -> {remote_item}", file=sys.stderr)
                        sftp.put(local_item, remote_item)
                        print(f"[SUCCESS] 上传成功: {item}", file=sys.stderr)
                    elif os.path.isdir(local_item):
                        # 跳过特定目录
                        if item in ['__pycache__', '.git', 'node_modules', '.venv', 'venv', 'logs', 'docs']:
                            print(f"[SKIP] 跳过目录: {item}", file=sys.stderr)
                            continue
                        print(f"[INFO] 进入目录: {item}", file=sys.stderr)
                        upload_recursive(local_item, remote_item)
                except PermissionError as e:
                    print(f"[ERROR] 权限错误 {local_item}: {e}", file=sys.stderr)
                    raise
                except Exception as e:
                    print(f"[ERROR] 处理失败 {item}: {str(e)}", file=sys.stderr)
                    raise
        
        upload_recursive(local_path, remote_path)
        
        print("[SUCCESS] 所有文件复制完成", file=sys.stderr)
        
        sftp.close()
        client.close()
        return True
    except Exception as e:
        print(f"[ERROR] 复制目录失败: {str(e)}", file=sys.stderr)
        raise Exception(f"复制目录失败: {str(e)}")

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': '参数不足'
        }))
        sys.exit(1)
    
    action = sys.argv[1]
    
    try:
        if action == 'test':
            # 测试SSH连接
            # python ssh_helper.py test <robot_ip>
            if len(sys.argv) < 3:
                raise Exception('缺少robot_ip参数')
            robot_ip = sys.argv[2]
            result = test_ssh_connection(robot_ip)
            print(json.dumps({
                'success': True,
                'connected': result
            }))
        
        elif action == 'exec':
            # 执行远程命令
            # python ssh_helper.py exec <robot_ip> <command>
            if len(sys.argv) < 4:
                raise Exception('缺少参数')
            robot_ip = sys.argv[2]
            command = sys.argv[3]
            output = execute_remote_command(robot_ip, command)
            print(json.dumps({
                'success': True,
                'output': output
            }))
        
        elif action == 'write':
            # 写入远程文件
            # python ssh_helper.py write <robot_ip> <remote_path> <content>
            if len(sys.argv) < 5:
                raise Exception('缺少参数')
            robot_ip = sys.argv[2]
            remote_path = sys.argv[3]
            content = sys.argv[4]
            write_remote_file(robot_ip, remote_path, content)
            print(json.dumps({
                'success': True
            }))
        
        elif action == 'copy':
            # 复制目录
            # python ssh_helper.py copy <robot_ip> <local_path> <remote_path>
            if len(sys.argv) < 5:
                raise Exception('缺少参数')
            robot_ip = sys.argv[2]
            local_path = sys.argv[3]
            remote_path = sys.argv[4]
            copy_directory(robot_ip, local_path, remote_path)
            print(json.dumps({
                'success': True
            }))
        
        else:
            raise Exception(f'未知操作: {action}')
    
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': str(e)
        }))
        sys.exit(1)

if __name__ == '__main__':
    main()
