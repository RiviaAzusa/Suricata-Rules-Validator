#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动脚本
"""

import os
import sys


def main():
    """主函数"""
    print("=" * 60)
    print("🛡️  Suricata规则管理器")
    print("=" * 60)
    print()

    # 检查环境变量
    key_password = os.getenv("KEY_PASSWORD")
    ssh_password = os.getenv("SSH_PASSWORD")

    if not key_password and not ssh_password:
        print("⚠️  警告: 未设置SSH认证信息")
        print("请设置环境变量:")
        print("  export KEY_PASSWORD='your_key_password'  # 私钥密码")
        print("  export SSH_PASSWORD='your_ssh_password'  # SSH密码")
        print()

    print("🚀 启动Web应用...")
    print("📍 访问地址: http://localhost:5000")
    print("🔧 功能:")
    print("   - 在线编辑Suricata规则文件")
    print("   - 保存并重载规则")
    print("   - 实时监控日志输出")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)

    # 导入并运行应用
    try:
        from app import app, socketio, init_ssh, start_monitoring

        # 初始化SSH连接
        if init_ssh():
            print("✅ SSH连接成功")
            # 自动启动监控
            if start_monitoring():
                print("✅ 日志监控已启动")
            else:
                print("❌ 日志监控启动失败")
        else:
            print("❌ SSH连接失败")

        print()
        print("🌐 Web服务器启动中...")

        # 启动Web应用
        socketio.run(app, host="0.0.0.0", port=5300, debug=False)

    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
