#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持续监控测试脚本
"""

import time
import threading
import signal
import sys
from ssh_manager import get_ssh_manager


class ContinuousMonitor:
    """持续监控类"""

    def __init__(self):
        self.ssh = get_ssh_manager()
        self.running = True
        self.threads = []
        self.captured_count = 0

        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """信号处理器，用于优雅退出"""
        print(f"\n收到退出信号 {signum}，正在停止监控...")
        self.stop()

    def stop(self):
        """停止监控"""
        self.running = False
        print("正在停止所有监控线程...")

        # 停止SSH tail命令
        if hasattr(self.ssh, "stop_tail_command"):
            self.ssh.stop_tail_command()

        # 等待线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)

        print(f"监控已停止，总共捕获了 {self.captured_count} 行日志")
        sys.exit(0)

    def suricata_log_callback(self, line):
        """Suricata日志回调函数"""
        if not self.running:
            return

        self.captured_count += 1
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Suricata: {line}")

    def dtrace_callback(self, line):
        """DTrace回调函数"""
        if not self.running:
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] DTrace: {line}")

    def start_suricata_monitoring(self):
        """启动Suricata日志监控"""
        print("启动Suricata日志持续监控...")
        print("监控命令: tail -f /var/log/suricata/suricata.log | grep '当前流'")

        try:
            # 先获取一些历史日志
            result = self.ssh.execute_command(
                'tail -n 5 /var/log/suricata/suricata.log | grep "当前流"'
            )
            if result["success"] and result["stdout"].strip():
                print("最近的历史日志:")
                lines = result["stdout"].strip().split("\n")
                for line in lines:
                    if line.strip():
                        print(f"  历史: {line}")

            # 启动实时监控
            thread = self.ssh.start_tail_command(
                'tail -f /var/log/suricata/suricata.log | grep "当前流"',
                self.suricata_log_callback,
            )
            self.threads.append(thread)
            print("✓ Suricata日志监控已启动")

        except Exception as e:
            print(f"✗ 启动Suricata监控失败: {e}")

    def start_dtrace_monitoring(self):
        """启动DTrace监控"""
        print("启动DTrace持续监控...")
        print(
            "监控命令: /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"
        )

        try:
            command = "cd /data/su7 && /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"
            thread = self.ssh.start_tail_command(command, self.dtrace_callback)
            self.threads.append(thread)
            print("✓ DTrace监控已启动")

        except Exception as e:
            print(f"✗ 启动DTrace监控失败: {e}")

    def start_monitoring(self, monitor_suricata=True, monitor_dtrace=True):
        """启动监控"""
        print("=" * 80)
        print("持续监控系统启动")
        print("=" * 80)

        # 检查SSH连接
        if not self.ssh.connected:
            print("✗ SSH连接失败，无法进行监控")
            return

        print("✓ SSH连接正常")

        # 启动监控
        if monitor_suricata:
            self.start_suricata_monitoring()

        if monitor_dtrace:
            self.start_dtrace_monitoring()

        print("\n监控已启动，按 Ctrl+C 停止监控")
        print("=" * 80)

        # 主循环
        try:
            while self.running:
                time.sleep(1)

                # 每30秒显示一次状态
                if self.captured_count > 0 and self.captured_count % 30 == 0:
                    print(f"\n[状态] 已运行，捕获了 {self.captured_count} 行日志")

        except KeyboardInterrupt:
            print("\n收到键盘中断，正在停止...")
            self.stop()


def test_connection():
    """测试连接"""
    print("测试SSH连接...")
    ssh = get_ssh_manager()

    if not ssh.connected:
        print("✗ SSH连接失败")
        return False

    print("✓ SSH连接成功")

    # 测试基本命令
    result = ssh.execute_command("echo 'SSH测试成功'")
    if result["success"]:
        print("✓ SSH命令执行正常")
        return True
    else:
        print("✗ SSH命令执行失败")
        return False


def main():
    """主函数"""
    print("持续监控测试脚本")
    print("支持的监控类型:")
    print("1. Suricata日志监控")
    print("2. DTrace监控")
    print("3. 同时监控两者")
    print()

    # 测试连接
    if not test_connection():
        print("连接测试失败，退出")
        return

    # 选择监控类型
    try:
        choice = input("请选择监控类型 (1/2/3，默认3): ").strip()
        if not choice:
            choice = "3"

        monitor_suricata = choice in ["1", "3"]
        monitor_dtrace = choice in ["2", "3"]

        # 创建监控器并启动
        monitor = ContinuousMonitor()
        monitor.start_monitoring(monitor_suricata, monitor_dtrace)

    except KeyboardInterrupt:
        print("\n用户取消操作")
    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    main()
