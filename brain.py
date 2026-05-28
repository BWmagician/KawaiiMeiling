import json
import re
import requests
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt5.QtCore import QThread, pyqtSignal

# 根据操作系统，条件导入 Windows 底层 API 指针，Mac 用户无需安装
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes


# ==================== 跨平台：前台应用与坐标边界检测 ====================
def get_frontmost_app_info():
    if sys.platform == "darwin":
        script = """
        tell application "System Events"
            try
                set frontApp to name of first application process whose frontmost is true
                tell process frontApp
                    set {l, t, r, b} to bounds of first window
                    return frontApp & "|||" & l & "," & t & "," & b
                end tell
            on error
                return "Unknown|||"
            end try
        end tell
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout:
                parts = result.stdout.strip().split("|||")
                app = parts[0] if len(parts) > 0 else "未知应用"
                bounds = parts[1] if (len(parts) > 1 and parts[1]) else ""
                return app, bounds
        except Exception:
            pass

    elif sys.platform == "win32":
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value if buf.value else "未知窗口"

                bounds_str = f"{rect.left},{rect.top},{rect.right},{rect.bottom}"
                return "活动窗口", bounds_str
        except Exception as e:
            print(f"[DEBUG-ERROR] Windows 窗口探测失败: {e}")

    return None, None


def query_local_ollama(api_url, model, text, source="clipboard"):
    print(f"\n[DEBUG-OLLAMA] 正在调用 Ollama 提炼摘要, 模型: {model}, 数据源: {source}")
    payload = {
        "model": model,
        "prompt": f"请分析以下客人的操作数据：\n'{text}'",
        "system": (
            "你是一个运行在本地的极简网页摘要提炼器。你需要分析客人的数据（如剪贴板或网页），"
            "用极为简短的一句话（8个字以内，越短越好）概括客人在干什么，绝对不许说任何废话。\n"
            "你必须只返回 JSON 格式，如下所示：\n"
            "{\n"
            '  "summary": "string"\n'
            "}"
        ),
        "format": "json",
        "stream": False,
        "options": {"num_predict": 50, "temperature": 0.1, "top_k": 10},
    }
    try:
        response = requests.post(
            api_url, json=payload, timeout=25, proxies={"http": None, "https": None}
        )
        print(f"[DEBUG-OLLAMA] 收到 HTTP 回应状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "{}").strip()
            print(f"[DEBUG-OLLAMA] 原始生成文本: {response_text}")

            json_match = re.search(r"(\{.*?\})", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            data = json.loads(response_text)
            summary = data.get("summary", "").strip()
            print(f"[DEBUG-OLLAMA] 摘要提炼成功! summary: '{summary}'")
            return summary
        else:
            print(f"[DEBUG-OLLAMA] Ollama HTTP 响应异常，内容: {response.text}")
    except Exception as e:
        print(f"[DEBUG-ERROR] 调用本地 Ollama 发生异常! 错误信息: {e}")
    return ""


# ==================== 接收 Chrome 插件发来数据的 HTTP 服务器 ====================
class LocalServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        if self.path == "/web_content":
            try:
                print("\n[DEBUG-SERVER] 收到来自插件/curl的 POST 请求 /web_content")
                content_length = int(self.headers["Content-Length"])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode("utf-8"))

                title = data.get("title", "")
                content = data.get("content", "")
                print(
                    f"[DEBUG-SERVER] 提取内容成功. 标题: '{title}', 内容字数: {len(content)}"
                )

                # 发送信号
                if hasattr(self.server, "emitter"):
                    self.server.emitter.web_content_received.emit(title, content)

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:
                print(f"[DEBUG-ERROR] 服务器处理 POST 失败: {e}")
                self.send_response(500)
                self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class LocalServerThread(QThread):
    web_content_received = pyqtSignal(str, str)

    def __init__(self, port=18088):
        super().__init__()
        self.port = port
        self.server = None

    def run(self):
        try:
            print(
                f"[DEBUG-SERVER] 本地 HTTP 接收服务正在 127.0.0.1:{self.port} 启动..."
            )
            self.server = HTTPServer(("127.0.0.1", self.port), LocalServerHandler)
            self.server.emitter = self
            self.server.serve_forever()
        except Exception as e:
            print(f"[DEBUG-ERROR] 本地服务器启动失败: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            print("[DEBUG-SERVER] 本地 HTTP 接收服务已安全关闭。")


# ==================== 异步线程：环境与剪贴板感知通道 ====================
class LocalSensingWorker(QThread):
    response_received = pyqtSignal(str, str, str, str, str)

    def __init__(self, config, raw_text, history, user_profile, source="clipboard"):
        super().__init__()
        self.config = config
        self.clipboard_text = raw_text
        self.history = history
        self.user_profile = user_profile
        self.source = source

    def run(self):
        print(f"\n[DEBUG-THREAD] LocalSensingWorker 线程启动，来源: {self.source}")
        summary = query_local_ollama(
            self.config["ollama_api_url"],
            self.config["ollama_model"],
            self.clipboard_text,
            self.source,
        )

        if not summary or summary in ["无", "空", "未知", "Unknown"]:
            print("[DEBUG-THREAD] 本地提炼内容无意义，静默退出线程保护Token。")
            return

        try:
            url = self.config["deepseek_api_url"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['deepseek_api_key']}",
            }

            system_prompt = (
                "你现在是《东方Project》中的红美铃（Hong Meiling），红魔馆的门番。\n"
                "你对红魔馆的同伴很忠诚，对馆外的用户十分友善，精通中华武术，经常打瞌睡。\n"
                f"根据记忆，你对客人的印象是：{self.user_profile}。\n"
                "请以此身份与用户对话。每次回答限制在3句话内，字数控制在35字以内。\n"
                "\n"
                "【重要：自主权控制标签系统】你必须在回复的内容末尾附带以下三个维度的标签指令：\n"
                "1. [ACTION: idle / sleep / talk]\n"
                "2. [MOVE: top_left / top_right / bottom_left / bottom_right / center]\n"
                "3. [PIN: lock / float] (固定/悬浮)"
            )

            context_messages = [{"role": "system", "content": system_prompt}]
            for h in self.history[-4:]:
                context_messages.append(h)

            user_message = f"【系统环境感知：客人目前在做：{summary}。请主动对客人进行一两句可爱的调侃。】"
            context_messages.append({"role": "user", "content": user_message})

            # 修复：从 config 中动态获取大模型名称，解决第三方代理报错问题
            model_name = self.config.get("deepseek_model", "deepseek-chat")
            print(f"[DEBUG-DEEPSEEK] 正在发起 API 请求, 目标模型: '{model_name}'...")

            data = {
                "model": model_name,
                "messages": context_messages,
                "temperature": 0.8,
            }

            response = requests.post(url, json=data, headers=headers, timeout=10)
            print(
                f"[DEBUG-DEEPSEEK] 收到 DeepSeek 回应，状态码: {response.status_code}"
            )
            if response.status_code == 200:
                result = response.json()
                raw_reply = result["choices"][0]["message"]["content"].strip()
                print(f"[DEBUG-DEEPSEEK] 生成原始内容: {raw_reply}")

                # 提取 ACTION
                action_tag = "idle"
                action_match = re.search(r"\[ACTION:\s*(\w+)\]", raw_reply)
                if action_match:
                    action_tag = action_match.group(1).lower()
                    raw_reply = re.sub(r"\[ACTION:\s*\w+\]", "", raw_reply).strip()

                # 提取位移
                move_tag = ""
                move_match = re.search(r"\[MOVE:\s*(\w+)\]", raw_reply)
                if move_match:
                    move_tag = move_match.group(1).lower()
                    raw_reply = re.sub(r"\[MOVE:\s*\w+\]", "", raw_reply).strip()

                # 提取固定
                pin_tag = ""
                pin_match = re.search(r"\[PIN:\s*(\w+)\]", raw_reply)
                if pin_match:
                    pin_tag = pin_match.group(1).lower()
                    raw_reply = re.sub(r"\[PIN:\s*\w+\]", "", raw_reply).strip()

                reply = raw_reply
                print(
                    f"[DEBUG-DEEPSEEK] 表情: '{action_tag}', 位移: '{move_tag}', 窗口锁定: '{pin_tag}'"
                )

                # 生成新画像
                updated_profile = self.user_profile
                try:
                    summary_prompt = (
                        f"请根据客人的行为：'{summary}'，"
                        f"以及你原来的记忆：'{self.user_profile}'，用一句话更新对客人的印象特征（20字以内）。"
                    )
                    summary_data = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": summary_prompt}],
                        "temperature": 0.5,
                    }
                    sum_res = requests.post(
                        url, json=summary_data, headers=headers, timeout=5
                    )
                    if sum_res.status_code == 200:
                        updated_profile = sum_res.json()["choices"][0]["message"][
                            "content"
                        ].strip()
                except Exception as e:
                    print(f"[DEBUG-ERROR] 更新用户画像失败: {e}")

                self.response_received.emit(
                    reply, action_tag, move_tag, pin_tag, updated_profile
                )
                print("[DEBUG-THREAD] 数据打包传送回主窗口，线程结束。")
            else:
                print(f"[DEBUG-ERROR] DeepSeek API 报错，信息: {response.text}")
        except Exception as e:
            print(f"[DEBUG-ERROR] 调用云端发生异常! 详细错误原因: {e}")


# ==================== 异步线程：主动聊天通道 ====================
class CloudChatWorker(QThread):
    response_received = pyqtSignal(str, str, str, str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config, user_input, history, user_profile):
        super().__init__()
        self.config = config
        self.user_input = user_input
        self.history = history
        self.user_profile = user_profile

    def run(self):
        try:
            current_app, _ = get_frontmost_app_info()
            url = self.config["deepseek_api_url"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['deepseek_api_key']}",
            }

            system_prompt = (
                "你现在是《东方Project》中的红美铃（Hong Meiling），红魔馆的门番。\n"
                "你对红魔馆的同伴很忠诚，对馆外的用户十分友善，精通中华武术，经常打瞌睡。\n"
                f"根据记忆，你对客人的印象是：{self.user_profile}。\n"
                "请以此身份与用户对话。每次回答限制在3句话内，字数控制在35字以内。\n"
                "\n"
                "【重要：自主权控制标签系统】你必须在回复的内容末尾附带以下三个维度的标签指令：\n"
                "1. [ACTION: idle / sleep / talk]\n"
                "2. [MOVE: top_left / top_right / bottom_left / bottom_right / center]\n"
                "3. [PIN: lock / float] (固定/悬浮)"
            )

            context_messages = [{"role": "system", "content": system_prompt}]
            for h in self.history[-4:]:
                context_messages.append(h)

            user_msg = self.user_input
            if current_app:
                user_msg = (
                    f"【系统环境：客人正在使用软件: {current_app}】\n{self.user_input}"
                )

            context_messages.append({"role": "user", "content": user_msg})

            model_name = self.config.get("deepseek_model", "deepseek-chat")
            data = {
                "model": model_name,
                "messages": context_messages,
                "temperature": 0.8,
            }
            response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                raw_reply = result["choices"][0]["message"]["content"].strip()

                # 1. ACTION
                action_tag = "idle"
                action_match = re.search(r"\[ACTION:\s*(\w+)\]", raw_reply)
                if action_match:
                    action_tag = action_match.group(1).lower()
                    raw_reply = re.sub(r"\[ACTION:\s*\w+\]", "", raw_reply).strip()

                # 2. MOVE
                move_tag = ""
                move_match = re.search(r"\[MOVE:\s*(\w+)\]", raw_reply)
                if move_match:
                    move_tag = move_match.group(1).lower()
                    raw_reply = re.sub(r"\[MOVE:\s*\w+\]", "", raw_reply).strip()

                # 3. PIN
                pin_tag = ""
                pin_match = re.search(r"\[PIN:\s*(\w+)\]", raw_reply)
                if pin_match:
                    pin_tag = pin_match.group(1).lower()
                    raw_reply = re.sub(r"\[PIN:\s*\w+\]", "", raw_reply).strip()

                reply = raw_reply

                # 提炼记忆
                updated_profile = self.user_profile
                try:
                    summary_prompt = (
                        f"请根据用户刚才说的话：'{self.user_input}'，"
                        f"以及你原来的记忆：'{self.user_profile}'，用一句话更新对客人的印象特征（20字以内）。"
                    )
                    summary_data = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": summary_prompt}],
                        "temperature": 0.5,
                    }
                    sum_res = requests.post(
                        url, json=summary_data, headers=headers, timeout=5
                    )
                    if sum_res.status_code == 200:
                        updated_profile = sum_res.json()["choices"][0]["message"][
                            "content"
                        ].strip()
                except Exception:
                    pass

                self.response_received.emit(
                    reply, action_tag, move_tag, pin_tag, updated_profile
                )
            else:
                self.error_occurred.emit(f"气路阻塞 (错误码: {response.status_code})")
        except Exception as e:
            # 修复：打印具体底层异常，拒绝“风沙太大”的无意义遮掩
            print(f"[DEBUG-ERROR] CloudChatWorker 异常: {e}")
            self.error_occurred.emit(f"风沙太大，我没听清客人的话。 (详情: {e})")
