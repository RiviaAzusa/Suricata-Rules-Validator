#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志监控与规则管理系统 - 服务器入口
"""

import uvicorn
import sys


def main():
    """启动服务器"""
    print("=" * 60)
    print("🚀 启动日志监控与规则管理系统")
    print("=" * 60)
    print("功能特性:")
    print("  ✓ 实时监控 DTrace 和 Suricata 日志")
    print("  ✓ 在线编辑 Suricata 规则文件")
    print("  ✓ 远程规则重载功能")
    print("  ✓ 日志过滤和分类显示")
    print("=" * 60)
    print("访问地址: http://localhost:8000")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)

    try:
        # 导入应用
        from src.enhanced_log_watcher import app

        # 启动服务器
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
