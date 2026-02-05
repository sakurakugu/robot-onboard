"""SSH 连接管理模块 - 处理远程机器狗的 SSH 连接和命令执行"""

import os
from typing import Optional, Tuple
import paramiko


class SSH管理器:
    """SSH 连接管理器 - 处理远程连接、命令执行和文件传输"""
    
    def __init__(self, 机器人IP: str, 用户名: str = "firefly", 密码: str = "firefly"):
        self.机器人IP = 机器人IP
        self.用户名 = 用户名
        self.密码 = 密码
        self.SSH客户端: Optional[paramiko.SSHClient] = None
    
    def 连接(self) -> bool:
        """连接到机器狗"""
        try:
            print(f"正在连接机器狗 {self.机器人IP}...")
            self.SSH客户端 = paramiko.SSHClient()
            self.SSH客户端.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.SSH客户端.connect(
                hostname=self.机器人IP,
                username=self.用户名,
                password=self.密码,
                timeout=10
            )
            print("✓ 成功连接到机器狗")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def 断开连接(self):
        """断开 SSH 连接"""
        if self.SSH客户端:
            self.SSH客户端.close()
            print("已断开连接")
    
    def 执行命令(self, command: str, use_sudo: bool = False) -> Tuple[bool, str, str]:
        """执行远程命令
        
        Args:
            command: 要执行的命令
            use_sudo: 是否使用 sudo 权限
            
        Returns:
            (成功标志, 标准输出, 错误输出)
        """
        if not self.SSH客户端:
            return False, "", "未连接到机器狗"
        
        try:
            if use_sudo:
                command = f"echo {self.密码} | sudo -S {command}"
            
            stdin, stdout, stderr = self.SSH客户端.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            out = stdout.read().decode('utf-8')
            err = stderr.read().decode('utf-8')
            
            return exit_status == 0, out, err
        except Exception as e:
            return False, "", str(e)
    
    def 写入配置文件(self, content: str, target_path: str, description: str = "配置文件") -> bool:
        """将内容写入配置文件（通过临时文件）
        
        Args:
            content: 文件内容
            target_path: 目标文件路径
            description: 文件描述，用于错误提示
        
        Returns:
            成功返回True，失败返回False
        """
        temp_file = "/tmp/" + target_path.split("/")[-1]
        
        # 写入临时文件
        write_cmd = f"cat > {temp_file} << 'EOF'\n{content}\nEOF"
        success, _, error = self.执行命令(write_cmd)
        if not success:
            print(f"✗ 写入临时文件失败: {error}")
            return False
        
        # 复制到目标位置
        success, _, error = self.执行命令(f"cp {temp_file} {target_path}", use_sudo=True)
        if not success:
            print(f"✗ 复制{description}失败: {error}")
            return False
        
        return True
    
    def 上传目录(self, local_path: str, remote_path: str) -> bool:
        """递归上传目录到远程机器狗
        
        Args:
            local_path: 本地目录路径
            remote_path: 远程目录路径
            
        Returns:
            成功返回True，失败返回False
        """
        if not self.SSH客户端:
            print("未连接到机器狗")
            return False

        sftp = self.SSH客户端.open_sftp()
        
        try:
            try:
                sftp.stat(remote_path)
            except FileNotFoundError:
                # 尝试创建远程目录
                self.执行命令(f"mkdir -p {remote_path}")
            
            for root, dirs, files in os.walk(local_path):
                relative_path = os.path.relpath(root, local_path)
                remote_root = os.path.join(remote_path, relative_path).replace("\\", "/")
                if relative_path == ".":
                    remote_root = remote_path
                
                # 确保远程目录存在
                try:
                    sftp.stat(remote_root)
                except FileNotFoundError:
                    self.执行命令(f"mkdir -p {remote_root}")
                
                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = os.path.join(remote_root, file).replace("\\", "/")
                    print(f"正在上传: {file} ...")
                    sftp.put(local_file, remote_file)
            print("✓ 文件上传完成")
            return True
        except Exception as e:
            print(f"✗ 上传失败: {e}")
            return False
        finally:
            sftp.close()
