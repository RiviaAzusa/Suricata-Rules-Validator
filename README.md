# Suricata规则验证器

一个基于Web的Suricata规则文件编辑和实时监控系统。

## 功能特性

- 🔧 **在线编辑**: 通过Web界面直接编辑远程服务器上的Suricata规则文件
- 💾 **实时保存**: 支持快捷键保存和自动保存功能
- 🔄 **规则重新加载**: 一键重新加载Suricata规则并验证加载状态
- 📊 **实时监控**: 同时监控Suricata日志和DTrace输出
- 🎨 **现代界面**: 基于Bootstrap 5的响应式设计
- ⚡ **实时通信**: 使用WebSocket实现实时日志推送

## 系统架构

```
┌─────────────────┐    WebSocket    ┌─────────────────┐    SSH    ┌─────────────────┐
│   Web Browser   │ ←──────────────→ │  Flask Server   │ ←────────→ │  Remote Server  │
│                 │                 │                 │           │                 │
│ - 规则编辑器     │                 │ - API接口       │           │ - Suricata      │
│ - 实时日志显示   │                 │ - SSH管理       │           │ - DTrace        │
│ - 状态监控      │                 │ - 日志转发      │           │ - 规则文件      │
└─────────────────┘                 └─────────────────┘           └─────────────────┘
```

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置SSH连接

编辑 `ssh_manager.py` 文件中的连接参数：

```python
ssh_manager = SSHManager(
    hostname="your-server-ip",
    port=22,
    username="your-username",
    private_key_path="/path/to/your/private/key",
)
```

### 3. 设置环境变量（可选）

```bash
export KEY_PASSWORD="your-private-key-password"
export SSH_PASSWORD="your-ssh-password"
```

### 4. 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 启动。

## 使用说明

### 规则编辑

1. 点击"加载规则"按钮从远程服务器加载当前规则文件
2. 在编辑器中修改规则内容
3. 使用 `Ctrl+S` (Windows/Linux) 或 `Cmd+S` (Mac) 保存规则
4. 点击"重新加载"按钮让Suricata重新加载规则

### 日志监控

- 系统会自动启动两种监控：
  - **Suricata日志**: 监控 `/var/log/suricata/suricata.log` 中包含"当前流"的日志
  - **DTrace监控**: 监控DTrace工具的输出
- 日志会实时显示在右侧面板
- 支持自动滚动和手动清空日志
- 显示每种日志类型的计数

### 状态指示

- **连接状态**: 显示与服务器的连接状态
- **监控状态**: 显示日志监控的运行状态
- **操作反馈**: 所有操作都有相应的成功/失败提示

## API接口

### 获取规则文件
```
GET /api/rules
```

### 保存规则文件
```
POST /api/rules
Content-Type: application/json

{
    "content": "规则文件内容"
}
```

### 重新加载规则
```
POST /api/reload-rules
```

## WebSocket事件

### 客户端监听事件

- `connect`: 连接成功
- `disconnect`: 连接断开
- `status`: 状态更新
- `suricata_log`: Suricata日志
- `dtrace_log`: DTrace日志

### 客户端发送事件

- `start_monitoring`: 启动监控
- `stop_monitoring`: 停止监控

## 技术栈

### 后端
- **Flask**: Web框架
- **Flask-SocketIO**: WebSocket支持
- **Paramiko**: SSH连接管理
- **Threading**: 多线程日志监控

### 前端
- **Bootstrap 5**: UI框架
- **CodeMirror**: 代码编辑器
- **Socket.IO**: 实时通信
- **Font Awesome**: 图标库

## 文件结构

```
Suricata-Rules-Validator/
├── app.py                 # Flask应用主文件
├── ssh_manager.py         # SSH连接管理器
├── test_tail_fix.py       # 测试脚本
├── requirements.txt       # Python依赖
├── README.md             # 项目说明
├── templates/
│   └── index.html        # 主页模板
└── static/
    ├── css/
    │   └── style.css     # 样式文件
    └── js/
        └── app.js        # 前端JavaScript
```

## 注意事项

1. 确保SSH私钥文件权限正确 (600)
2. 确保目标服务器上的Suricata和DTrace工具可用
3. 监控功能需要相应的文件和命令权限
4. 建议在生产环境中使用HTTPS和适当的身份验证

## 故障排除

### SSH连接失败
- 检查服务器地址、端口和用户名
- 验证私钥文件路径和权限
- 确认服务器SSH服务正常运行

### 规则重新加载失败
- 检查Suricata配置文件语法
- 验证suricatasc命令路径
- 查看Suricata服务状态

### 日志监控无输出
- 确认日志文件路径存在
- 检查文件读取权限
- 验证grep过滤条件

## 许可证

MIT License 