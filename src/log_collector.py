#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时日志收集器
从远程服务器实时读取日志并保存到本地文件
"""

import time
import threading
import signal
import sys
from datetime import datetime
from pathlib import Path
import logging
from src.ssh_manager import get_ssh_manager


class LogCollector:
    """实时日志收集器"""

    def __init__(self, log_dir="logs"):
        self.ssh = get_ssh_manager()
        self.running = True
        self.threads = []
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # 日志文件路径
        self.suricata_log_file = self.log_dir / "suricata_logs.log"
        self.dtrace_log_file = self.log_dir / "dtrace_logs.log"

        # 文件锁，确保线程安全写入
        self.suricata_lock = threading.Lock()
        self.dtrace_lock = threading.Lock()

        # 统计信息
        self.suricata_count = 0
        self.dtrace_count = 0

        # 设置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.log_dir / "collector.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """信号处理器，用于优雅退出"""
        self.logger.info(f"收到退出信号 {signum}，正在停止日志收集...")
        self.stop()

    def stop(self):
        """停止日志收集"""
        self.running = False
        self.logger.info("正在停止所有收集线程...")

        # 停止SSH tail命令
        if hasattr(self.ssh, "stop_tail_command"):
            self.ssh.stop_tail_command()

        # 等待线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=3)

        self.logger.info("日志收集已停止")
        self.logger.info(f"Suricata日志: {self.suricata_count} 行")
        self.logger.info(f"DTrace日志: {self.dtrace_count} 行")
        sys.exit(0)

    def write_to_file(self, file_path, content, lock):
        """线程安全地写入文件 - 与auto_add_log.py保持一致的写入方式"""
        with lock:
            try:
                with open(file_path, "a") as f:
                    f.write(content + "\n")
            except Exception as e:
                self.logger.error(f"写入文件 {file_path} 失败: {e}")

    def suricata_log_callback(self, line):
        """Suricata日志回调函数"""
        if not self.running:
            return

        self.suricata_count += 1

        # 生成带时间戳的日志条目，格式与auto_add_log.py一致
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[**] [{timestamp}] Suricata: {line}"

        # 写入本地文件
        self.write_to_file(self.suricata_log_file, log_entry, self.suricata_lock)

        # 控制台输出（可选）
        if self.suricata_count % 10 == 0:  # 每10条日志输出一次状态
            self.logger.info(f"Suricata日志已收集 {self.suricata_count} 行")

    def dtrace_callback(self, line):
        """DTrace回调函数"""
        if not self.running:
            return

        self.dtrace_count += 1

        # 生成带时间戳的日志条目，格式与auto_add_log.py一致
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[**] [{timestamp}] DTrace: {line}"

        # 写入本地文件
        self.write_to_file(self.dtrace_log_file, log_entry, self.dtrace_lock)

        # 控制台输出（可选）
        if self.dtrace_count % 10 == 0:  # 每10条日志输出一次状态
            self.logger.info(f"DTrace日志已收集 {self.dtrace_count} 行")

    def start_suricata_collection(self):
        """启动Suricata日志收集"""
        self.logger.info("启动Suricata日志收集...")
        self.logger.info(
            "监控命令: tail -f /var/log/suricata/suricata.log | grep '当前流'"
        )

        try:
            # 先获取一些历史日志并保存
            result = self.ssh.execute_command(
                'tail -n 10 /var/log/suricata/suricata.log | grep "当前流"'
            )
            if result["success"] and result["stdout"].strip():
                self.logger.info("保存历史Suricata日志...")
                lines = result["stdout"].strip().split("\n")
                for line in lines:
                    if line.strip():
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        log_entry = f"[**] [{timestamp}] Suricata(历史): {line}"
                        self.write_to_file(
                            self.suricata_log_file,
                            log_entry,
                            self.suricata_lock,
                        )

            # 启动实时监控
            thread = self.ssh.start_tail_command(
                'tail -f /var/log/suricata/suricata.log | grep "当前流"',
                self.suricata_log_callback,
            )
            self.threads.append(thread)
            self.logger.info("✓ Suricata日志收集已启动")

        except Exception as e:
            self.logger.error(f"✗ 启动Suricata收集失败: {e}")

    def start_dtrace_collection(self):
        """启动DTrace日志收集"""
        self.logger.info("启动DTrace日志收集...")
        self.logger.info(
            "监控命令: /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"
        )

        try:
            command = "cd /data/su7 && /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"
            thread = self.ssh.start_tail_command(command, self.dtrace_callback)
            self.threads.append(thread)
            self.logger.info("✓ DTrace日志收集已启动")

        except Exception as e:
            self.logger.error(f"✗ 启动DTrace收集失败: {e}")

    def rotate_logs_if_needed(self):
        """如果日志文件过大，进行轮转"""
        max_size = 100 * 1024 * 1024  # 100MB

        for log_file in [self.suricata_log_file, self.dtrace_log_file]:
            if log_file.exists() and log_file.stat().st_size > max_size:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{log_file.stem}_{timestamp}.txt"
                backup_path = log_file.parent / backup_name

                try:
                    log_file.rename(backup_path)
                    self.logger.info(f"日志文件已轮转: {log_file} -> {backup_path}")
                except Exception as e:
                    self.logger.error(f"日志轮转失败: {e}")

    def start_collection(self, collect_suricata=True, collect_dtrace=True):
        """启动日志收集"""
        self.logger.info("=" * 80)
        self.logger.info("实时日志收集系统启动")
        self.logger.info(f"日志保存目录: {self.log_dir.absolute()}")
        self.logger.info("=" * 80)

        # 检查SSH连接
        if not self.ssh.connected:
            self.logger.error("✗ SSH连接失败，无法进行日志收集")
            return

        self.logger.info("✓ SSH连接正常")

        # 创建日志文件并写入开始标记
        if collect_suricata:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            start_marker = f"[**] [{timestamp}] === Suricata日志收集开始 ==="
            self.write_to_file(self.suricata_log_file, start_marker, self.suricata_lock)
            self.start_suricata_collection()

        if collect_dtrace:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            start_marker = f"[**] [{timestamp}] === DTrace日志收集开始 ==="
            self.write_to_file(self.dtrace_log_file, start_marker, self.dtrace_lock)
            self.start_dtrace_collection()

        self.logger.info("\n日志收集已启动，按 Ctrl+C 停止收集")
        self.logger.info("=" * 80)

        # 主循环
        try:
            last_status_time = time.time()
            while self.running:
                time.sleep(1)

                # 每60秒显示一次状态和检查日志轮转
                current_time = time.time()
                if current_time - last_status_time >= 60:
                    self.logger.info(
                        f"[状态] Suricata: {self.suricata_count} 行, "
                        f"DTrace: {self.dtrace_count} 行"
                    )
                    self.rotate_logs_if_needed()
                    last_status_time = current_time

        except KeyboardInterrupt:
            self.logger.info("\n收到键盘中断，正在停止...")
            self.stop()

    def get_log_stats(self):
        """获取日志统计信息"""
        stats = {
            "suricata_count": self.suricata_count,
            "dtrace_count": self.dtrace_count,
            "suricata_file": str(self.suricata_log_file),
            "dtrace_file": str(self.dtrace_log_file),
            "suricata_size": self.suricata_log_file.stat().st_size
            if self.suricata_log_file.exists()
            else 0,
            "dtrace_size": self.dtrace_log_file.stat().st_size
            if self.dtrace_log_file.exists()
            else 0,
        }
        return stats


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
    print("实时日志收集器")
    print("支持的收集类型:")
    print("1. Suricata日志收集")
    print("2. DTrace日志收集")
    print("3. 同时收集两者")
    print()

    # 测试连接
    if not test_connection():
        print("连接测试失败，退出")
        return

    # 选择收集类型
    try:
        choice = input("请选择收集类型 (1/2/3，默认3): ").strip()
        if not choice:
            choice = "3"

        collect_suricata = choice in ["1", "3"]
        collect_dtrace = choice in ["2", "3"]

        # 选择日志保存目录
        log_dir = input("请输入日志保存目录 (默认: logs): ").strip()
        if not log_dir:
            log_dir = "logs"

        # 创建收集器并启动
        collector = LogCollector(log_dir)
        collector.start_collection(collect_suricata, collect_dtrace)

    except KeyboardInterrupt:
        print("\n用户取消操作")
    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == "__main__":
    main()
