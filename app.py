#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suricata规则管理Web应用
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
from ssh_manager import get_ssh_manager

app = Flask(__name__)
app.config["SECRET_KEY"] = "suricata-rules-validator-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量
ssh_manager = None
monitoring_active = False
monitoring_threads = []


def init_ssh():
    """初始化SSH连接"""
    global ssh_manager
    ssh_manager = get_ssh_manager()
    return ssh_manager.connected


@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/rules", methods=["GET"])
def get_rules():
    """获取规则文件内容"""
    try:
        if not ssh_manager or not ssh_manager.connected:
            return jsonify({"error": "SSH连接未建立"}), 500

        content = ssh_manager.read_file("/data/su7/rules/suricata.rules")
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rules", methods=["POST"])
def save_rules():
    """保存规则文件"""
    try:
        if not ssh_manager or not ssh_manager.connected:
            return jsonify({"error": "SSH连接未建立"}), 500

        data = request.get_json()
        content = data.get("content", "")

        # 保存文件
        ssh_manager.write_file("/data/su7/rules/suricata.rules", content)

        return jsonify({"message": "规则文件保存成功"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reload-rules", methods=["POST"])
def reload_rules():
    """重载规则"""
    try:
        if not ssh_manager or not ssh_manager.connected:
            return jsonify({"error": "SSH连接未建立"}), 500

        # 执行重载命令
        result = ssh_manager.execute_command("/data/su7/bin/suricatasc -c reload-rules")

        if result["success"]:
            try:
                # 尝试解析JSON响应
                response = json.loads(result["stdout"].strip())
                if response.get("message") == "done" and response.get("return") == "OK":
                    return jsonify({"success": True, "message": "规则重载成功"})
                else:
                    return jsonify(
                        {"success": False, "message": f"规则重载失败: {response}"}
                    )
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接返回输出
                return jsonify(
                    {"success": True, "message": f"命令执行完成: {result['stdout']}"}
                )
        else:
            return jsonify(
                {"success": False, "message": f"命令执行失败: {result['stderr']}"}
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def suricata_log_callback(line):
    """Suricata日志回调函数"""
    if monitoring_active:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        socketio.emit(
            "log_message", {"type": "suricata", "timestamp": timestamp, "message": line}
        )


def dtrace_callback(line):
    """DTrace回调函数"""
    if monitoring_active:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        socketio.emit(
            "log_message", {"type": "dtrace", "timestamp": timestamp, "message": line}
        )


def start_monitoring():
    """启动日志监控"""
    global monitoring_active, monitoring_threads

    if not ssh_manager or not ssh_manager.connected:
        return False

    monitoring_active = True
    monitoring_threads = []

    try:
        # 启动Suricata日志监控
        suricata_thread = ssh_manager.start_tail_command(
            'tail -f /var/log/suricata/suricata.log | grep "当前流"',
            suricata_log_callback,
        )
        monitoring_threads.append(suricata_thread)

        # 启动DTrace监控
        dtrace_command = "cd /data/su7 && /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"
        dtrace_thread = ssh_manager.start_tail_command(dtrace_command, dtrace_callback)
        monitoring_threads.append(dtrace_thread)

        return True
    except Exception as e:
        print(f"启动监控失败: {e}")
        return False


@socketio.on("connect")
def handle_connect():
    """客户端连接"""
    print("客户端已连接")
    emit("status", {"message": "连接成功"})


@socketio.on("disconnect")
def handle_disconnect():
    """客户端断开连接"""
    print("客户端已断开连接")


@socketio.on("start_monitoring")
def handle_start_monitoring():
    """启动监控"""
    if start_monitoring():
        emit("status", {"message": "监控已启动"})
    else:
        emit("status", {"message": "监控启动失败"})


if __name__ == "__main__":
    # 初始化SSH连接
    if init_ssh():
        print("SSH连接成功")
        # 自动启动监控
        start_monitoring()
        print("日志监控已启动")
    else:
        print("SSH连接失败")

    # 启动Web应用
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
