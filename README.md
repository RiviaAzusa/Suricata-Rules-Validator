# Suricata Rules Validator

一个基于 FastAPI 的实时日志监控和 Suricata 规则管理系统。

## 🚀 快速开始

### 安装依赖
```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 启动服务
```bash
python run_server.py
```

访问 http://localhost:8000 开始使用。

## ✨ 核心功能

- **实时日志监控** - 同时监控 DTrace 和 Suricata 日志文件
- **规则在线编辑** - 远程编辑和保存 Suricata 规则文件
- **规则重载** - 一键重载规则并验证结果
- **日志过滤** - 按类型过滤和分类显示日志
- **状态监控** - SSH 和 WebSocket 连接状态实时监控

## 🛠️ 技术栈

- **后端**: FastAPI + WebSocket
- **文件监控**: Watchdog
- **SSH 连接**: Paramiko
- **前端**: 原生 JavaScript + Socket.IO

## 📁 项目结构

```
src/
├── enhanced_log_watcher.py  # 主应用 (FastAPI)
├── log_collector.py         # 日志收集器
├── ssh_manager.py          # SSH 连接管理
└── log_watcher.py          # 备用日志监控
logs/                       # 日志文件目录
run_server.py              # 服务启动入口
run_log_collector.py      # 日志收集器启动入口
```

## ⚙️ 配置

编辑 `src/ssh_manager.py` 配置 SSH 连接：
- 远程主机地址和端口
- SSH 用户名和私钥路径
- Suricata 规则文件路径

## 📝 使用说明

1. **日志监控**: 启动后自动显示实时日志，支持类型过滤
2. **规则编辑**: 点击"加载规则" → 编辑 → "保存规则"
3. **规则重载**: 点击"重载规则"执行远程重载命令

## 🔧 故障排除

- **SSH 连接失败**: 检查网络和 SSH 配置
- **日志不显示**: 确认日志文件路径和权限
- **规则编辑失败**: 验证远程文件路径和权限

---

**License**: MIT | **Python**: >=3.13 