#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH连接管理器 - 用于Web应用
基于ssh_simulator.py，提供Web应用所需的SSH操作接口
"""

import paramiko
import os
import threading
import socket
from paramiko import AuthenticationException


class SSHManager:
    def __init__(self, hostname, port, username, private_key_path):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.private_key_path = private_key_path
        self.client = None
        self.connected = False
        self.lock = threading.Lock()
        self.tail_threads = []  # 存储tail线程

    def load_private_key(self, key_password=None):
        """加载私钥文件"""
        try:
            if not os.path.exists(self.private_key_path):
                raise Exception(f"私钥文件不存在: {self.private_key_path}")

            # 尝试加载不同类型的私钥
            key_types = [
                paramiko.RSAKey,
                paramiko.Ed25519Key,
                paramiko.ECDSAKey,
                paramiko.DSSKey,
            ]

            for key_type in key_types:
                try:
                    private_key = key_type.from_private_key_file(
                        self.private_key_path, password=key_password
                    )
                    return private_key
                except paramiko.PasswordRequiredException:
                    if key_password is None:
                        raise
                    continue
                except (paramiko.SSHException, ValueError):
                    continue

            raise Exception("无法加载私钥文件")

        except paramiko.PasswordRequiredException:
            raise Exception("私钥文件需要密码")
        except Exception as e:
            raise Exception(f"加载私钥时出错: {e}")

    def connect(self, key_password=None, ssh_password=None):
        """建立SSH连接"""
        with self.lock:
            try:
                if self.connected and self.client:
                    return True

                # 加载私钥
                private_key = self.load_private_key(key_password)

                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # 尝试使用私钥认证
                try:
                    self.client.connect(
                        hostname=self.hostname,
                        port=self.port,
                        username=self.username,
                        pkey=private_key,
                        timeout=10,
                    )
                    self.connected = True
                    return True
                except AuthenticationException:
                    # 如果私钥认证失败，尝试密码认证
                    if ssh_password:
                        self.client.connect(
                            hostname=self.hostname,
                            port=self.port,
                            username=self.username,
                            password=ssh_password,
                            timeout=10,
                        )
                        self.connected = True
                        return True
                    else:
                        raise Exception("私钥认证失败，且未提供SSH密码")

            except Exception as e:
                self.connected = False
                if self.client:
                    self.client.close()
                    self.client = None
                raise Exception(f"SSH连接失败: {e}")

    def execute_command(self, command, timeout=30):
        """执行命令并返回结果"""
        if not self.connected or not self.client:
            raise Exception("SSH未连接")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)

            # 等待命令执行完成
            exit_status = stdout.channel.recv_exit_status()

            output = stdout.read().decode("utf-8", errors="ignore")
            error = stderr.read().decode("utf-8", errors="ignore")

            return {
                "exit_status": exit_status,
                "stdout": output,
                "stderr": error,
                "success": exit_status == 0,
            }
        except Exception as e:
            raise Exception(f"执行命令失败: {e}")

    def read_file(self, file_path):
        """读取远程文件内容"""
        try:
            sftp = self.client.open_sftp()
            with sftp.file(file_path, "r") as f:
                content = f.read().decode("utf-8", errors="ignore")
            sftp.close()
            return content
        except Exception as e:
            raise Exception(f"读取文件失败: {e}")

    def write_file(self, file_path, content):
        """写入远程文件"""
        try:
            sftp = self.client.open_sftp()
            with sftp.file(file_path, "w") as f:
                f.write(content.encode("utf-8"))
            sftp.close()
            return True
        except Exception as e:
            raise Exception(f"写入文件失败: {e}")

    def start_tail_command(self, command, callback):
        """启动tail命令并持续读取输出"""

        def tail_worker():
            try:
                # 使用get_pty=True来获得伪终端，这对于tail -f很重要
                stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)

                # 设置非阻塞模式
                stdout.channel.settimeout(1.0)

                while True:
                    try:
                        # 逐字符读取，直到遇到换行符
                        line = ""
                        while True:
                            char = stdout.read(1)
                            if not char:
                                break
                            char = char.decode("utf-8", errors="ignore")
                            if char == "\n":
                                if line.strip():  # 只处理非空行
                                    callback(line.strip())
                                line = ""
                                break
                            else:
                                line += char

                    except socket.timeout:
                        # 超时是正常的，继续循环
                        continue
                    except Exception as e:
                        callback(f"读取错误: {e}")
                        break

            except Exception as e:
                callback(f"命令执行错误: {e}")

        thread = threading.Thread(target=tail_worker)
        thread.daemon = True
        thread.start()
        self.tail_threads.append(thread)  # 添加到线程列表
        return thread

    def stop_tail_command(self):
        """停止所有tail命令"""
        # 清理线程列表，移除已结束的线程
        self.tail_threads = [t for t in self.tail_threads if t.is_alive()]

    def close(self):
        """关闭SSH连接"""
        with self.lock:
            self.connected = False
            if self.client:
                self.client.close()
                self.client = None
            # 清理tail线程
            self.tail_threads = []


# 全局SSH管理器实例
ssh_manager = None


def get_ssh_manager():
    """获取SSH管理器实例"""
    global ssh_manager
    if ssh_manager is None:
        # 使用与ssh_simulator.py相同的连接参数
        ssh_manager = SSHManager(
            hostname="10.168.27.239",
            port=7722,
            username="root",
            private_key_path="box",
        )

        # 尝试连接
        try:
            key_password = os.getenv("KEY_PASSWORD")
            ssh_password = os.getenv("SSH_PASSWORD")
            ssh_manager.connect(key_password, ssh_password)
        except Exception as e:
            print(f"SSH连接失败: {e}")

    return ssh_manager
