# Suricata规则管理器

一个基于Web的Suricata规则文件管理和日志监控系统。

## 功能特性

- 🔧 **在线编辑**: 直接在浏览器中编辑Suricata规则文件
- 💾 **保存规则**: 将修改后的规则保存到远程服务器
- ⚡ **重载规则**: 执行规则重载命令并验证结果
- 📊 **实时监控**: 同时监控Suricata日志和DTrace输出
- 🌐 **Web界面**: 简洁美观的用户界面

## 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt
```

## 配置

### SSH连接配置

在 `ssh_manager.py` 中配置SSH连接参数：

```python
ssh_manager = SSHManager(
    hostname="10.168.27.239",    # 服务器地址
    port=7722,                   # SSH端口
    username="root",             # 用户名
    private_key_path="/Users/azusa/.ssh/box",  # 私钥路径
)
```

### 环境变量

设置SSH认证信息（可选）：

```bash
export KEY_PASSWORD="your_private_key_password"  # 私钥密码
export SSH_PASSWORD="your_ssh_password"          # SSH密码
```

## 启动应用

### 方式1: 使用启动脚本（推荐）

```bash
python run.py
```

### 方式2: 直接运行

```bash
python app.py
```

## 访问应用

启动后在浏览器中访问：

```
http://localhost:5000
```

## 使用说明

### 规则编辑

1. **加载规则**: 点击"🔄 加载"按钮从服务器加载当前规则文件
2. **编辑规则**: 在左侧编辑器中修改规则内容
3. **保存规则**: 点击"💾 保存"按钮将修改保存到服务器
4. **重载规则**: 点击"⚡ 重载规则"按钮执行规则重载

### 日志监控

- 右侧面板会实时显示两种类型的日志：
  - **[Suricata]**: Suricata日志输出（绿色）
  - **[DTrace]**: DTrace监控输出（橙色）
- 点击"🗑️ 清空"按钮可以清空日志显示

### 状态指示

- **编辑器状态栏**: 显示当前操作状态
- **连接状态栏**: 显示SSH连接和监控状态
- **通知消息**: 右上角显示操作结果通知

## 文件结构

```
.
├── app.py              # Flask应用主文件
├── ssh_manager.py      # SSH连接管理器
├── run.py              # 启动脚本
├── requirements.txt    # Python依赖
├── templates/
│   └── index.html      # Web界面模板
└── README_WEB.md       # 使用说明
```

## 技术栈

- **后端**: Flask + Flask-SocketIO
- **前端**: HTML + CSS + JavaScript + Socket.IO
- **SSH**: Paramiko
- **实时通信**: WebSocket

## 注意事项

1. **权限要求**: 确保SSH用户有权限读写规则文件和执行重载命令
2. **网络连接**: 确保能够SSH连接到目标服务器
3. **文件路径**: 确认规则文件路径 `/data/su7/rules/suricata.rules` 正确
4. **命令路径**: 确认重载命令路径 `/data/su7/bin/suricatasc` 正确

## 故障排除

### SSH连接失败

1. 检查服务器地址、端口、用户名是否正确
2. 确认私钥文件路径和权限
3. 检查网络连接

### 规则重载失败

1. 检查Suricata服务是否运行
2. 确认suricatasc命令路径正确
3. 检查规则文件语法是否正确

### 日志监控无输出

1. 确认日志文件路径正确
2. 检查DTrace工具是否可用
3. 确认Suricata进程ID正确

## 开发说明

如需修改监控命令或文件路径，请编辑 `app.py` 中的相关配置：

```python
# Suricata日志监控命令
'tail -f /var/log/suricata/suricata.log | grep "当前流"'

# DTrace监控命令
"cd /data/su7 && /data/su7/dtraceattach -P /data/su7/dtraceattach.bpf.o -B /data/su7/bin/suricata -p 3372788"

# 规则文件路径
'/data/su7/rules/suricata.rules'

# 重载命令
'/data/su7/bin/suricatasc -c reload-rules'
``` 