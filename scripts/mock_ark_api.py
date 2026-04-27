#!/usr/bin/env python3
"""
mock_ark_api.py - 模拟 Ark 3D API 服务器

本地运行，模拟供应商 API 的完整流程：
1. POST /api/v3/contents/generations/tasks  -> 创建任务
2. GET  /api/v3/contents/generations/tasks/{id}  -> 查询任务状态

用法：
    python mock_ark_api.py [--port 8080]
"""

import argparse
import json
import time
import uuid
import threading
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 任务存储 (线程安全)
tasks = {}
tasks_lock = threading.Lock()

# 配置
TASK_PROCESS_TIME = 5  # 任务处理时间（秒）


def now_ms():
    return int(time.time() * 1000)


class MockArkHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[MockArk] {args[0]}")

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # POST /api/v3/contents/generations/tasks - 创建任务
        if path == "/api/v3/contents/generations/tasks":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            try:
                req = json.loads(body)
            except:
                return self.send_json(400, {"error": "invalid json"})

            model = req.get("model", "")
            content = req.get("content", [])

            # 创建任务
            task_id = f"task_{uuid.uuid4().hex[:16]}"
            with tasks_lock:
                tasks[task_id] = {
                    "id": task_id,
                    "model": model,
                    "content": content,
                    "status": "queued",
                    "created_at": now_ms(),
                    "submit_request": req,
                    "result_file_url": None,
                }

            # 异步模拟处理（5秒后变为 succeeded）
            def process_task(task_id):
                time.sleep(TASK_PROCESS_TIME)
                with tasks_lock:
                    if task_id in tasks:
                        tasks[task_id]["status"] = "succeeded"
                        tasks[task_id]["completed_at"] = now_ms()
                        tasks[task_id]["content"] = {
                            "file_url": f"https://tos.example.com/mock-results/{task_id}/model.glb",
                            "format": "glb"
                        }
                print(f"[MockArk] Task {task_id} completed ✅")

            threading.Thread(target=process_task, args=(task_id,), daemon=True).start()

            print(f"[MockArk] Created task {task_id} for model {model}")
            return self.send_json(200, {
                "id": task_id,
                "status": "queued",
                "created_at": tasks[task_id]["created_at"] / 1000
            })

        self.send_json(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # GET /api/v3/contents/generations/tasks/{id} - 查询任务
        if path.startswith("/api/v3/contents/generations/tasks/"):
            task_id = path.split("/")[-1]

            with tasks_lock:
                if task_id not in tasks:
                    return self.send_json(404, {"error": "task not found"})
                task = tasks[task_id]

            # 模拟处理中状态
            if task["status"] == "queued":
                # 随机决定是否还在排队
                if random.random() < 0.3:
                    return self.send_json(200, {
                        "id": task_id,
                        "status": "running",
                        "model": task["model"]
                    })

            if task["status"] == "succeeded":
                return self.send_json(200, {
                    "id": task_id,
                    "status": "succeeded",
                    "model": task["model"],
                    "content": task["content"]
                })

            return self.send_json(200, {
                "id": task_id,
                "status": task["status"],
                "model": task["model"]
            })

        self.send_json(404, {"error": "not found"})

    # 允许 HEAD
    def do_HEAD(self):
        self.send_response(200)


def main():
    parser = argparse.ArgumentParser(description="Mock Ark 3D API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--process-time", type=int, default=5,
                       help="Task processing time in seconds")
    args = parser.parse_args()

    global TASK_PROCESS_TIME
    TASK_PROCESS_TIME = args.process_time

    server = HTTPServer(("0.0.0.0", args.port), MockArkHandler)
    print(f"🎭 Mock Ark API Server running on http://0.0.0.0:{args.port}")
    print(f"   POST /api/v3/contents/generations/tasks        - 创建任务")
    print(f"   GET  /api/v3/contents/generations/tasks/{{id}} - 查询任务")
    print(f"   任务将在 {TASK_PROCESS_TIME} 秒后自动完成")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
