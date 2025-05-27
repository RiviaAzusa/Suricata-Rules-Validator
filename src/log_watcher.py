import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator
import json
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import aiofiles

app = FastAPI(title="日志实时监控系统")

LOG_FILE = "/Users/azusa/projects/seven/Logs-Watcher/logs/dtrace_logs.log"
current_file_size = 0
log_queue = asyncio.Queue()


class LogFileHandler(FileSystemEventHandler):
    """文件监控处理器"""

    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        super().__init__()

    def on_modified(self, event):
        """当文件被修改时触发 - 只处理LOG_FILE的修改"""
        # 只处理文件修改事件，且必须是我们要监控的LOG_FILE
        if (
            event.event_type == "modified"
            and not event.is_directory
            and os.path.abspath(event.src_path) == os.path.abspath(self.log_file_path)
        ):
            print(f"检测到日志文件修改: {event.src_path}")
            # 创建新的事件循环来运行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.read_new_content())
            finally:
                loop.close()

    async def read_new_content(self):
        """读取文件新增内容"""
        global current_file_size

        try:
            if not os.path.exists(self.log_file_path):
                return

            # 获取当前文件大小
            new_size = os.path.getsize(self.log_file_path)

            if new_size > current_file_size:
                # 读取新增内容
                async with aiofiles.open(
                    self.log_file_path, "r", encoding="utf-8"
                ) as f:
                    await f.seek(current_file_size)
                    new_content = await f.read()

                    # 按行分割并发送每一行
                    lines = new_content.strip().split("\n")
                    for line in lines:
                        if line.strip():  # 忽略空行
                            await log_queue.put(
                                {
                                    "timestamp": datetime.now().isoformat(),
                                    "content": line.strip(),
                                }
                            )

                current_file_size = new_size

        except Exception as e:
            print(f"读取文件时出错: {e}")


# 初始化文件监控
def setup_file_watcher():
    """设置文件监控"""
    global current_file_size

    # 确保日志文件存在
    if not os.path.exists(LOG_FILE):
        Path(LOG_FILE).touch()
        print(f"创建日志文件: {LOG_FILE}")

    # 获取初始文件大小
    current_file_size = os.path.getsize(LOG_FILE)
    print(f"开始监控日志文件: {LOG_FILE}")
    print(f"初始文件大小: {current_file_size} 字节")

    # 设置文件监控 - 直接监控LOG_FILE文件所在的目录，但只处理LOG_FILE的变化
    event_handler = LogFileHandler(LOG_FILE)
    observer = Observer()
    # 监控LOG_FILE所在的目录
    log_dir = os.path.dirname(LOG_FILE)
    print(f"监控目录: {log_dir}")
    observer.schedule(
        event_handler,
        path=log_dir,
        recursive=False,
    )
    observer.start()

    return observer


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
    <title>实时日志监控</title>
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
        
        .log-container {
            height: calc(100vh - 80px);
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
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .log-timestamp {
            color: #888;
            font-size: 12px;
            margin-bottom: 4px;
        }
        
        .log-content {
            color: #00ff00;
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
        .log-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .log-container::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        
        .log-container::-webkit-scrollbar-thumb {
            background: #00ff00;
            border-radius: 4px;
        }
        
        .log-container::-webkit-scrollbar-thumb:hover {
            background: #00cc00;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">🔍 实时日志监控系统</div>
        <div class="status">
            <div class="status-indicator" id="statusIndicator"></div>
            <span id="statusText">连接中...</span>
        </div>
    </div>
    
    <div class="log-container" id="logContainer">
        <div class="log-entry">
            <div class="log-timestamp">系统启动时间: <span id="startTime"></span></div>
            <div class="log-content">等待日志数据...</div>
        </div>
    </div>

    <script>
        let eventSource = null;
        let isConnected = false;
        const logContainer = document.getElementById('logContainer');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const startTime = document.getElementById('startTime');
        
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
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            const timestamp = new Date(logData.timestamp).toLocaleString('zh-CN');
            
            logEntry.innerHTML = `
                <div class="log-timestamp">${timestamp}</div>
                <div class="log-content">${escapeHtml(logData.content)}</div>
            `;
            
            logContainer.appendChild(logEntry);
            
            // 自动滚动到底部
            logContainer.scrollTop = logContainer.scrollHeight;
            
            // 限制日志条数，避免内存占用过多
            const logEntries = logContainer.querySelectorAll('.log-entry');
            if (logEntries.length > 1000) {
                logEntries[0].remove();
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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
        if not os.path.exists(LOG_FILE):
            return {"logs": []}

        async with aiofiles.open(LOG_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            # 返回最近100条日志
            recent_logs = lines[-100:] if len(lines) > 100 else lines

            return {
                "logs": [
                    {"timestamp": datetime.now().isoformat(), "content": line}
                    for line in recent_logs
                ]
            }
    except Exception as e:
        return {"error": f"读取日志失败: {str(e)}"}


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    if observer:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
