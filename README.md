# 日志监控和规则编辑系统

这是一个基于Flask的Web应用，用于实时监控日志文件并在线编辑Suricata规则。

## 功能特性

### 日志监控
- 同时监控 `dtrace_logs.log` 和 `suricata_logs.log` 两个日志文件
- 实时显示新增的日志内容
- 支持按日志类型过滤显示（全部/Suricata/DTrace）
- 提供清空当前页面日志的功能
- 使用WebSocket实现实时推送

### 规则编辑
- 在线读取远程Suricata规则文件 (`/data/su7/rules/suricata.rules`)
- 在线编辑规则内容
- 保存规则到远程服务器
- 执行规则重载命令 (`/data/su7/bin/suricatasc -c reload-rules`)
- 自动检测重载结果（期望返回 `{"message": "done", "return": "OK"}`)

### 系统状态
- SSH连接状态监控
- WebSocket连接状态监控
- 实时状态指示器

## 项目结构

```
Logs-Watcher/
├── src/
│   ├── app.py              # Flask后端应用
│   ├── log_collector.py    # 日志收集器
│   ├── ssh_manager.py      # SSH连接管理器
│   ├── log_watcher.py      # 原有的日志监控（FastAPI版本）
│   └── static/
│       └── index.html      # 前端页面
├── logs/                   # 日志文件目录
│   ├── dtrace_logs.log     # DTrace日志
│   └── suricata_logs.log   # Suricata日志
├── requirements.txt        # Python依赖
├── start_web_app.py       # Web应用启动脚本
└── README.md              # 项目说明
```

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置SSH连接

确保 `src/ssh_manager.py` 中的SSH连接配置正确：
- 主机地址
- 端口
- 用户名
- 私钥路径

### 3. 启动应用

```bash
python start_web_app.py
```

### 4. 访问Web界面

打开浏览器访问：http://localhost:5000

## 使用说明

### 日志监控
1. 启动应用后，左侧面板会自动显示实时日志
2. 使用顶部的过滤按钮选择要显示的日志类型
3. 点击"清空日志"按钮可以清空当前显示的日志

### 规则编辑
1. 点击"加载规则"按钮从远程服务器加载当前规则文件
2. 在文本编辑器中修改规则内容
3. 点击"保存规则"按钮将修改保存到远程服务器
4. 点击"重载规则"按钮执行规则重载命令

### 状态监控
- 右上角显示SSH和WebSocket的连接状态
- 绿色圆点表示连接正常，红色圆点表示连接断开

## 技术架构

### 后端 (Flask)
- **Flask**: Web框架
- **Flask-SocketIO**: WebSocket支持，实现实时日志推送
- **Watchdog**: 文件系统监控，检测日志文件变化
- **Paramiko**: SSH客户端，用于远程文件操作和命令执行

### 前端
- **原生JavaScript**: 无框架依赖
- **Socket.IO**: WebSocket客户端
- **响应式设计**: 适配不同屏幕尺寸

### 特性
- **前后端分离**: RESTful API + WebSocket
- **实时监控**: 文件变化实时推送到前端
- **错误处理**: 完善的错误处理和用户反馈
- **状态管理**: 连接状态实时监控

## API接口

### 日志相关
- `GET /api/logs/history` - 获取历史日志
- `POST /api/logs/clear` - 清空日志文件

### 规则相关
- `GET /api/rules/read` - 读取远程规则文件
- `POST /api/rules/save` - 保存规则文件
- `POST /api/rules/reload` - 重载规则

### 系统状态
- `GET /api/ssh/status` - 获取SSH连接状态

### WebSocket事件
- `new_log` - 新日志推送
- `connect/disconnect` - 连接状态

## 注意事项

1. 确保SSH连接配置正确，否则规则编辑功能无法使用
2. 日志文件路径需要根据实际情况调整
3. 远程规则文件路径和重载命令需要根据实际环境配置
4. 建议在生产环境中使用HTTPS和适当的安全措施

## 故障排除

### SSH连接失败
- 检查网络连接
- 验证SSH配置（主机、端口、用户名、私钥）
- 确保远程服务器SSH服务正常

### 日志不显示
- 检查日志文件是否存在
- 确认日志收集器是否正常运行
- 查看控制台错误信息

### 规则编辑失败
- 确认SSH连接正常
- 检查远程文件路径和权限
- 验证重载命令是否正确 