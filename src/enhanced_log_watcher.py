import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator
import json
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import aiofiles
from pydantic import BaseModel

from src.ssh_manager import get_ssh_manager

app = FastAPI(title="日志实时监控与规则管理系统")

# 日志文件路径
DTRACE_LOG_FILE = "logs/dtrace_logs.log"
SURICATA_LOG_FILE = "logs/suricata_logs.log"

# 全局变量
current_dtrace_size = 0
current_suricata_size = 0
log_queue = asyncio.Queue()

# SSH管理器
ssh_manager = None


class RuleEditRequest(BaseModel):
    content: str


class LogFileHandler(FileSystemEventHandler):
    """文件监控处理器 - 支持多个日志文件"""

    def __init__(self, log_files: dict):
        self.log_files = log_files  # {file_path: file_type}
        super().__init__()

    def on_modified(self, event):
        """当文件被修改时触发"""
        if event.event_type == "modified" and not event.is_directory:
            abs_path = os.path.abspath(event.src_path)

            # 检查是否是我们监控的文件
            for log_file, log_type in self.log_files.items():
                if abs_path == os.path.abspath(log_file):
                    print(f"检测到{log_type}日志文件修改: {event.src_path}")
                    # 创建新的事件循环来运行异步任务
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self.read_new_content(log_file, log_type)
                        )
                    finally:
                        loop.close()
                    break

    async def read_new_content(self, log_file: str, log_type: str):
        """读取文件新增内容"""
        global current_dtrace_size, current_suricata_size

        try:
            if not os.path.exists(log_file):
                return

            # 获取当前文件大小
            new_size = os.path.getsize(log_file)

            # 根据文件类型获取当前大小
            if log_type == "dtrace":
                current_size = current_dtrace_size
            else:  # suricata
                current_size = current_suricata_size

            if new_size > current_size:
                # 读取新增内容
                async with aiofiles.open(log_file, "r", encoding="utf-8") as f:
                    await f.seek(current_size)
                    new_content = await f.read()

                    # 按行分割并发送每一行
                    lines = new_content.strip().split("\n")
                    for line in lines:
                        if line.strip():  # 忽略空行
                            await log_queue.put(
                                {
                                    "timestamp": datetime.now().isoformat(),
                                    "content": line.strip(),
                                    "type": log_type,
                                    "source": log_type.upper(),
                                }
                            )

                # 更新文件大小
                if log_type == "dtrace":
                    current_dtrace_size = new_size
                else:
                    current_suricata_size = new_size

        except Exception as e:
            print(f"读取{log_type}文件时出错: {e}")


def setup_file_watcher():
    """设置文件监控"""
    global current_dtrace_size, current_suricata_size

    # 监控的日志文件
    log_files = {DTRACE_LOG_FILE: "dtrace", SURICATA_LOG_FILE: "suricata"}

    # 确保日志文件存在并获取初始大小
    for log_file, log_type in log_files.items():
        if not os.path.exists(log_file):
            Path(log_file).touch()
            print(f"创建{log_type}日志文件: {log_file}")

        size = os.path.getsize(log_file)
        if log_type == "dtrace":
            current_dtrace_size = size
        else:
            current_suricata_size = size

        print(f"开始监控{log_type}日志文件: {log_file} (初始大小: {size} 字节)")

    # 设置文件监控
    event_handler = LogFileHandler(log_files)
    observer = Observer()

    # 监控logs目录
    log_dir = os.path.dirname(DTRACE_LOG_FILE)
    print(f"监控目录: {log_dir}")
    observer.schedule(event_handler, path=log_dir, recursive=False)
    observer.start()

    return observer


def get_ssh_connection():
    """获取SSH连接"""
    global ssh_manager
    if ssh_manager is None:
        ssh_manager = get_ssh_manager()
    return ssh_manager


# 启动时设置文件监控
observer = setup_file_watcher()


async def log_stream() -> AsyncGenerator[str, None]:
    """SSE日志流生成器"""
    try:
        while True:
            # 等待新的日志消息
            log_data = await log_queue.get()

            # 格式化为SSE格式
            sse_data = f"data: {json.dumps(log_data)}\n\n"
            yield sse_data

    except asyncio.CancelledError:
        print("日志流已断开")
    except Exception as e:
        print(f"日志流错误: {e}")


@app.get("/")
async def get_index():
    """返回主页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日志监控与规则管理系统</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background-color: #1a1a1a;
            color: #00ff00;
            height: 100vh;
            overflow: hidden;
        }
        
        .header {
            background-color: #2d2d2d;
            padding: 15px 20px;
            border-bottom: 2px solid #00ff00;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .title {
            font-size: 24px;
            font-weight: bold;
            color: #00ff00;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #ff0000;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.connected {
            background-color: #00ff00;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .btn {
            background-color: #333;
            color: #00ff00;
            border: 1px solid #00ff00;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .btn:hover {
            background-color: #00ff00;
            color: #1a1a1a;
        }
        
        .main-container {
            display: flex;
            height: calc(100vh - 80px);
        }
        
        .log-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .rules-panel {
            width: 400px;
            background-color: #2a2a2a;
            border-left: 2px solid #00ff00;
            display: flex;
            flex-direction: column;
        }
        
        .panel-header {
            background-color: #333;
            padding: 10px 15px;
            border-bottom: 1px solid #00ff00;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .log-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background-color: #1a1a1a;
        }
        
        .log-entry {
            margin-bottom: 8px;
            padding: 8px 12px;
            background-color: #2a2a2a;
            border-left: 3px solid #00ff00;
            border-radius: 4px;
            font-size: 14px;
            line-height: 1.4;
            word-wrap: break-word;
            animation: fadeIn 0.3s ease-in;
        }
        
        .log-entry.dtrace {
            border-left-color: #00ccff;
        }
        
        .log-entry.suricata {
            border-left-color: #ff6600;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .log-timestamp {
            color: #888;
            font-size: 12px;
            margin-bottom: 4px;
        }
        
        .log-source {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
            margin-right: 8px;
        }
        
        .log-source.dtrace {
            background-color: #00ccff;
            color: #1a1a1a;
        }
        
        .log-source.suricata {
            background-color: #ff6600;
            color: #1a1a1a;
        }
        
        .log-content {
            color: #00ff00;
        }
        
        .rules-editor {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 15px;
        }
        
        .rules-textarea {
            flex: 1;
            background-color: #1a1a1a;
            color: #00ff00;
            border: 1px solid #333;
            padding: 10px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 12px;
            resize: none;
            outline: none;
        }
        
        .rules-actions {
            margin-top: 10px;
            display: flex;
            gap: 10px;
        }
        
        .filter-controls {
            padding: 10px 20px;
            background-color: #2a2a2a;
            border-bottom: 1px solid #333;
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .filter-btn {
            background-color: #333;
            color: #888;
            border: 1px solid #555;
            padding: 5px 12px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s;
        }
        
        .filter-btn.active {
            background-color: #00ff00;
            color: #1a1a1a;
            border-color: #00ff00;
        }
        
        .error-message {
            color: #ff4444;
            text-align: center;
            padding: 20px;
            background-color: #2a1a1a;
            border: 1px solid #ff4444;
            border-radius: 4px;
            margin: 20px;
        }
        
        /* 滚动条样式 */
        .log-container::-webkit-scrollbar,
        .rules-textarea::-webkit-scrollbar {
            width: 8px;
        }
        
        .log-container::-webkit-scrollbar-track,
        .rules-textarea::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        
        .log-container::-webkit-scrollbar-thumb,
        .rules-textarea::-webkit-scrollbar-thumb {
            background: #00ff00;
            border-radius: 4px;
        }
        
        .log-container::-webkit-scrollbar-thumb:hover,
        .rules-textarea::-webkit-scrollbar-thumb:hover {
            background: #00cc00;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">🔍 日志监控与规则管理系统</div>
        <div class="controls">
            <div class="status">
                <div class="status-indicator" id="statusIndicator"></div>
                <span id="statusText">连接中...</span>
            </div>
        </div>
    </div>
    
    <div class="main-container">
        <div class="log-panel">
            <div class="filter-controls">
                <span>日志过滤:</span>
                <button class="filter-btn active" data-filter="all">全部</button>
                <button class="filter-btn" data-filter="dtrace">DTrace</button>
                <button class="filter-btn" data-filter="suricata">Suricata</button>
                <span style="margin-left: 20px;">总计: <span id="logCount">0</span> 条</span>
            </div>
            
            <div class="log-container" id="logContainer">
                <div class="log-entry">
                    <div class="log-timestamp">系统启动时间: <span id="startTime"></span></div>
                    <div class="log-content">等待日志数据...</div>
                </div>
            </div>
        </div>
        
        <div class="rules-panel">
            <div class="panel-header">
                <span>Suricata 规则编辑</span>
                <button class="btn" id="loadRulesBtn">加载规则</button>
            </div>
            
            <div class="rules-editor">
                <textarea class="rules-textarea" id="rulesTextarea" placeholder="点击'加载规则'按钮加载远程规则文件..."></textarea>
                
                <div class="rules-actions">
                    <button class="btn" id="saveRulesBtn">保存规则</button>
                    <button class="btn" id="reloadRulesBtn">重载规则</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let eventSource = null;
        let isConnected = false;
        let currentFilter = 'all';
        let logCount = 0;
        
        const logContainer = document.getElementById('logContainer');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const startTime = document.getElementById('startTime');
        const logCountElement = document.getElementById('logCount');
        const rulesTextarea = document.getElementById('rulesTextarea');
        
        // 设置启动时间
        startTime.textContent = new Date().toLocaleString('zh-CN');
        
        function updateStatus(connected) {
            isConnected = connected;
            if (connected) {
                statusIndicator.classList.add('connected');
                statusText.textContent = '已连接';
            } else {
                statusIndicator.classList.remove('connected');
                statusText.textContent = '连接断开';
            }
        }
        
        function addLogEntry(logData) {
            // 检查过滤器
            if (currentFilter !== 'all' && currentFilter !== logData.type) {
                return;
            }
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${logData.type}`;
            logEntry.dataset.type = logData.type;
            
            const timestamp = new Date(logData.timestamp).toLocaleString('zh-CN');
            
            logEntry.innerHTML = `
                <div class="log-timestamp">${timestamp}</div>
                <div class="log-content">
                    <span class="log-source ${logData.type}">${logData.source}</span>
                    ${escapeHtml(logData.content)}
                </div>
            `;
            
            logContainer.appendChild(logEntry);
            logCount++;
            logCountElement.textContent = logCount;
            
            // 自动滚动到底部
            logContainer.scrollTop = logContainer.scrollHeight;
            
            // 限制日志条数，避免内存占用过多
            const logEntries = logContainer.querySelectorAll('.log-entry');
            if (logEntries.length > 1000) {
                logEntries[0].remove();
                logCount--;
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function filterLogs(filterType) {
            currentFilter = filterType;
            const logEntries = logContainer.querySelectorAll('.log-entry');
            let visibleCount = 0;
            
            logEntries.forEach(entry => {
                if (filterType === 'all' || entry.dataset.type === filterType) {
                    entry.style.display = 'block';
                    visibleCount++;
                } else {
                    entry.style.display = 'none';
                }
            });
            
            // 更新过滤按钮状态
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`[data-filter="${filterType}"]`).classList.add('active');
        }
        
        function connectSSE() {
            if (eventSource) {
                eventSource.close();
            }
            
            eventSource = new EventSource('/logs/stream');
            
            eventSource.onopen = function(event) {
                console.log('SSE连接已建立');
                updateStatus(true);
            };
            
            eventSource.onmessage = function(event) {
                try {
                    const logData = JSON.parse(event.data);
                    addLogEntry(logData);
                } catch (e) {
                    console.error('解析日志数据失败:', e);
                }
            };
            
            eventSource.onerror = function(event) {
                console.error('SSE连接错误:', event);
                updateStatus(false);
                
                // 3秒后重连
                setTimeout(() => {
                    console.log('尝试重新连接...');
                    connectSSE();
                }, 3000);
            };
        }
        
        // 规则管理功能
        async function loadRules() {
            try {
                const response = await fetch('/rules/load');
                const data = await response.json();
                
                if (data.success) {
                    rulesTextarea.value = data.content;
                    alert('规则加载成功');
                } else {
                    alert('加载规则失败: ' + data.error);
                }
            } catch (error) {
                alert('加载规则失败: ' + error.message);
            }
        }
        
        async function saveRules() {
            try {
                const response = await fetch('/rules/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: rulesTextarea.value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('规则保存成功');
                } else {
                    alert('保存规则失败: ' + data.error);
                }
            } catch (error) {
                alert('保存规则失败: ' + error.message);
            }
        }
        
        async function reloadRules() {
            try {
                const response = await fetch('/rules/reload', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('规则重载成功: ' + data.message);
                } else {
                    alert('规则重载失败: ' + data.error);
                }
            } catch (error) {
                alert('规则重载失败: ' + error.message);
            }
        }
        
        // 事件监听器
        document.addEventListener('DOMContentLoaded', function() {
            // 过滤按钮
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    filterLogs(this.dataset.filter);
                });
            });
            
            // 规则管理按钮
            document.getElementById('loadRulesBtn').addEventListener('click', loadRules);
            document.getElementById('saveRulesBtn').addEventListener('click', saveRules);
            document.getElementById('reloadRulesBtn').addEventListener('click', reloadRules);
        });
        
        // 页面加载时连接SSE
        window.addEventListener('load', connectSSE);
        
        // 页面卸载时关闭连接
        window.addEventListener('beforeunload', function() {
            if (eventSource) {
                eventSource.close();
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/logs/stream")
async def stream_logs(request: Request):
    """SSE端点，流式传输日志"""
    return StreamingResponse(
        log_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@app.get("/logs/history")
async def get_log_history():
    """获取历史日志"""
    try:
        logs = []

        # 读取DTrace日志
        if os.path.exists(DTRACE_LOG_FILE):
            async with aiofiles.open(DTRACE_LOG_FILE, "r", encoding="utf-8") as f:
                content = await f.read()
                lines = [line.strip() for line in content.split("\n") if line.strip()]
                for line in lines[-50:]:  # 最近50条
                    logs.append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "content": line,
                            "type": "dtrace",
                            "source": "DTRACE",
                        }
                    )

        # 读取Suricata日志
        if os.path.exists(SURICATA_LOG_FILE):
            async with aiofiles.open(SURICATA_LOG_FILE, "r", encoding="utf-8") as f:
                content = await f.read()
                lines = [line.strip() for line in content.split("\n") if line.strip()]
                for line in lines[-50:]:  # 最近50条
                    logs.append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "content": line,
                            "type": "suricata",
                            "source": "SURICATA",
                        }
                    )

        # 按时间排序
        logs.sort(key=lambda x: x["timestamp"])

        return {"logs": logs}
    except Exception as e:
        return {"error": f"读取日志失败: {str(e)}"}


@app.get("/rules/load")
async def load_rules():
    """加载远程规则文件"""
    try:
        ssh = get_ssh_connection()
        if not ssh.connected:
            raise HTTPException(status_code=500, detail="SSH连接未建立")

        content = ssh.read_file("/data/su7/rules/suricata.rules")
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/rules/save")
async def save_rules(request: RuleEditRequest):
    """保存规则文件"""
    try:
        ssh = get_ssh_connection()
        if not ssh.connected:
            raise HTTPException(status_code=500, detail="SSH连接未建立")

        ssh.write_file("/data/su7/rules/suricata.rules", request.content)
        return {"success": True, "message": "规则保存成功"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/rules/reload")
async def reload_rules():
    """重载规则"""
    try:
        ssh = get_ssh_connection()
        if not ssh.connected:
            raise HTTPException(status_code=500, detail="SSH连接未建立")

        result = ssh.execute_command("/data/su7/bin/suricatasc -c reload-rules")

        if result["success"]:
            # 检查返回结果是否包含成功信息
            output = result["stdout"].strip()
            try:
                import json as json_lib

                response_data = json_lib.loads(output)
                if (
                    response_data.get("message") == "done"
                    and response_data.get("return") == "OK"
                ):
                    return {"success": True, "message": "规则重载成功"}
                else:
                    return {"success": False, "error": f"规则重载失败: {output}"}
            except:
                # 如果不是JSON格式，直接返回输出
                return {"success": True, "message": f"规则重载完成: {output}"}
        else:
            return {"success": False, "error": result["stderr"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    if observer:
        observer.stop()
        observer.join()

    global ssh_manager
    if ssh_manager:
        ssh_manager.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
