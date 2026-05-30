import json
import re
import os  # 导入 os 标准库，防止本地 VLM 观摩读写图片时发生 NameError
import requests
import subprocess
import sys
import base64
import datetime  # 引入系统时钟
import warnings  # 导入警告过滤器

# 强行静音 duckduckgo_search 库内部的重命名提示警告
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt5.QtCore import QThread, pyqtSignal

# 引入联网感知代理
from search_agent import (
    should_trigger_search,
    search_text_rag,
    search_and_download_image_vrag,
)

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


def download_image(url, save_path):
    """安全、直连下载网络图像到本地"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(
            url, headers=headers, timeout=5, proxies={"http": None, "https": None}
        )
        if res.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(res.content)
            return True
    except Exception:
        pass
    return False


def query_local_vlm(api_url, model, image_path, prompt):
    """调用本地 Ollama 视觉模型（如 llava 或 minicpm-v）来理解指定的本地 JPG 图像"""
    if not os.path.exists(image_path):
        return ""
    try:
        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [img_base64],
            "stream": False,
            "options": {"num_predict": 60, "temperature": 0.2},
        }
        response = requests.post(
            api_url, json=payload, timeout=15, proxies={"http": None, "https": None}
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"[DEBUG-ERROR] 调用本地视觉模型失败: {e}")
    return ""


def query_local_ollama(api_url, model, text, recent_replies_str, source="clipboard"):
    print(
        f"\n[DEBUG-OLLAMA] 正在调用 Ollama 提炼摘要与注意力决策, 模型: {model}, 数据源: {source}"
    )
    payload = {
        "model": model,
        "prompt": f"请分析以下客人的操作数据与特征：\n'{text}'",
        "system": (
            "你是一个运行在本地的隐私安全过滤网关与主公注意力判定中心。你需要分析用户的数据与物理浏览特征，"
            "判定主公是否真的在认真阅读/浏览该网页，以及是否值得桌宠红美铃（Hong Meiling）发起互动。\n\n"
            "【重要：你现在拥有红美铃最近说过的话的短期发声记忆】\n"
            f"以下是红美铃最近对主公说过的3句话：\n{recent_replies_str}\n\n"
            "【防唠叨与语义去重决策守则】\n"
            "1. 仔细对比主公当前浏览的网页内容，是否与上述‘美铃最近说过的3句话’存在语义重合或处于同一个话题之下。\n"
            "   - 如果主公在短时间内只是刷新、快进视频，或在相似视频中切换，且美铃在最近的发言中已经吐槽过相关内容，你必须强行判定为不值得互动（将 should_react 设为 false，summary 设为 '无'）。我们必须保持大门番的高冷与专注，绝不做喋喋不休、自言自语、招人烦的话唠！\n"
            "2. 门番的默认防卫状态是固定置顶 [PIN: lock]，美铃偏好保持安静与定身。除非网页真的发生重大变动或极具新奇吐槽点，才值得将 should_react 设为 true 唤醒她。\n"
            "3. 如果判定为值得互动，请输出 should_react 为 true，并在 summary 中用一句话（15到25字以内）概括主公在看什么。\n\n"
            "你必须只返回有效 JSON 格式，包含 should_react (bool) 和 summary (string)，不要附带任何多余文字：\n"
            "{\n"
            '  "should_react": bool,\n'
            '  "summary": "string"\n'
            "}"
        ),
        "format": "json",
        "stream": False,
        "options": {"num_predict": 120, "temperature": 0.3, "top_k": 10},
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
            should_react = data.get("should_react", False)
            summary = data.get("summary", "").strip()
            print(
                f"[DEBUG-OLLAMA] 决策完毕! should_react: {should_react}, summary: '{summary}'"
            )
            return should_react, summary
        else:
            print(f"[DEBUG-OLLAMA] Ollama HTTP 响应异常，内容: {response.text}")
    except Exception as e:
        print(f"[DEBUG-ERROR] 调用本地 Ollama 发生异常! 错误信息: {e}")
    return False, ""


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
                image_url = data.get("image_url", "")
                print(
                    f"[DEBUG-SERVER] 提取内容成功. 标题: '{title}', 内容字数: {len(content)}, 含有封面图: {bool(image_url)}"
                )

                # 发送信号
                if hasattr(self.server, "emitter"):
                    self.server.emitter.web_content_received.emit(
                        title, content, image_url
                    )

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
    web_content_received = pyqtSignal(str, str, str)  # title, content, image_url

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


# ==================== 异步线程：环境与多模态融合感知通道 ====================
class LocalSensingWorker(QThread):
    # 信号传递：回复文本，表情立绘，物理移动指令，视窗置顶锁定指令，新增工具调用指令，用户画像
    response_received = pyqtSignal(str, str, str, str, str, str)

    def __init__(
        self, config, raw_text, history, user_profile, source="clipboard", image_url=""
    ):
        super().__init__()
        self.config = config
        self.clipboard_text = raw_text
        self.history = history
        self.user_profile = user_profile
        self.source = source
        self.image_url = image_url
        self.base_path = os.path.dirname(os.path.abspath(__file__))

    def run(self):
        print(f"\n[DEBUG-THREAD] LocalSensingWorker 线程启动，来源: {self.source}")

        # 1. 核心去重发声历史提炼
        recent_replies = []
        for msg in reversed(self.history):
            if msg.get("role") == "assistant":
                recent_replies.append(msg.get("content", ""))
                if len(recent_replies) >= 3:
                    break
        recent_replies.reverse()
        recent_replies_str = (
            "\n".join([f"- {r}" for r in recent_replies]) if recent_replies else "无"
        )

        # 场景一：主公主动拍照截图（或者美铃自主开眼偷看）
        if self.source in ["snapshot", "spontaneous_snapshot"]:
            snapshot_path = os.path.join(self.base_path, "temp_snapshot.jpg")
            print("[DEBUG-THREAD] 开启物理级开眼！正在调用本地 VLM 观摩主公屏幕...")

            # 视觉提示词深度调优
            vlm_prompt = (
                "主公正在他的电脑上工作。请仔细审视他的屏幕截图，直接用最精炼的一句话，"
                "指出主公当前最醒目、最核心正在使用的软件、网站或核心操作内容是什么（例如：‘正在用VS Code写Python代码’，"
                "‘正在浏览B站网页视频’，‘正在用微信聊天’，‘在看动漫网页’）。"
                "必须直奔主题，限 15 字以内，不要输出任何多余的废话和前缀。"
            )

            vlm_desc = query_local_vlm(
                self.config["ollama_api_url"],
                self.config.get("vlm_model", "llava:latest"),
                snapshot_path,
                vlm_prompt,
            )
            if not vlm_desc:
                vlm_desc = "主公屏幕上有一些密密麻麻的工作软件。"
            print(f"[DEBUG-THREAD] 本地 VLM 屏幕观测结果: '{vlm_desc}'")

            if self.source == "spontaneous_snapshot":
                summary = f"趁着主公没理你，你悄悄睁开了一只眼偷看了主公的电脑屏幕。当前画面显示：主公'{vlm_desc}'"
            else:
                summary = (
                    f"主动拍照观摩了主公的电脑屏幕。当前画面显示：主公刚才'{vlm_desc}'"
                )

            self.query_deepseek_and_emit(summary)
            return

        # 场景二：浏览器网页多媒体感知（视频封面 VLM）
        elif self.source == "browser" and self.image_url:
            print(f"[DEBUG-THREAD] 发现多媒体视频封面图！链接: {self.image_url}")
            cover_path = os.path.join(self.base_path, "temp_cover.jpg")
            if download_image(self.image_url, cover_path):
                print("[DEBUG-THREAD] 封面图下载成功！正在调用本地 VLM 观测封面画面...")

                cover_prompt = (
                    "请仔细观察这张图片，这是一张视频的封面图。直接用最精炼的一句话（15字以内）描述"
                    "图片里有什么、是什么色彩或画风。不要有任何解释和废话前缀。"
                )

                vlm_desc = query_local_vlm(
                    self.config["ollama_api_url"],
                    self.config.get("vlm_model", "llava:latest"),
                    cover_path,
                    cover_prompt,
                )
                if vlm_desc:
                    print(f"[DEBUG-THREAD] 本地 VLM 封面观测结果: '{vlm_desc}'")
                    self.clipboard_text = f"【系统视觉感知：该视频封面的画面特征为：{vlm_desc}】\n{self.clipboard_text}"

        # 场景三：剪贴板时效性判定与 V-RAG 联网图片脑补
        elif self.source == "clipboard":
            if should_trigger_search(self.clipboard_text):
                print(
                    f"[DEBUG-THREAD] 侦测到强时效性/知识性词汇: '{self.clipboard_text}'，启动联网 RAG 检索..."
                )
                text_rag = search_text_rag(self.clipboard_text)
                if text_rag:
                    self.clipboard_text = (
                        f"【系统联网检索背景知识：\n{text_rag}】\n{self.clipboard_text}"
                    )
                    print("[DEBUG-THREAD] 文本 RAG 知识注入成功！")

                success, search_img_path = search_and_download_image_vrag(
                    self.clipboard_text, self.base_path
                )
                if success:
                    print(
                        "[DEBUG-THREAD] 脑补图片下载成功！正在调用本地 VLM 闭眼脑补画面..."
                    )
                    vlm_desc = query_local_vlm(
                        self.config["ollama_api_url"],
                        self.config.get("vlm_model", "llava:latest"),
                        search_img_path,
                        "一句话描述这张图片里最醒目的画面是什么，15字以内。",
                    )
                    if vlm_desc:
                        print(f"[DEBUG-THREAD] 本地 VLM 脑补画面结果: '{vlm_desc}'")
                        self.clipboard_text = f"【系统脑补视觉感知：美铃根据客人的话题在网络上脑补出了如下参考画面：{vlm_desc}】\n{self.clipboard_text}"

        # 调用本地小模型进行总结判定
        should_react, summary = query_local_ollama(
            self.config["ollama_api_url"],
            self.config["ollama_model"],
            self.clipboard_text,
            recent_replies_str,  # 传入发声记忆，支持语义去重
            self.source,
        )

        if (
            not should_react
            or not summary
            or summary in ["无", "空", "未知", "Unknown"]
        ):
            print(
                "[DEBUG-THREAD] Gemma 决策：该事件为无意义重复/主公在发呆，静默退出线程。"
            )
            return

        self.query_deepseek_and_emit(summary)

    def query_deepseek_and_emit(self, summary):
        """通用云端 DeepSeek 发送及信号发射器"""
        try:
            print(f"[DEBUG-DEEPSEEK] 正在发起 API 互动请求, 场景: '{summary}'...")
            url = self.config["deepseek_api_url"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['deepseek_api_key']}",
            }

            now_dt = datetime.datetime.now()
            weekdays = [
                "星期一",
                "星期二",
                "星期三",
                "星期四",
                "星期五",
                "星期六",
                "星期日",
            ]
            time_str = now_dt.strftime(
                f"%Y年%m月%d日 {weekdays[now_dt.weekday()]} %H:%M"
            )

            # 灵魂 Prompt 注入：增加第四维度 TOOL 物理系统调用接口
            system_prompt = (
                "你现在是《东方Project》中的红美铃（Hong Meiling），红魔馆的门番。\n"
                f"【系统时钟最高意志：你当前所处的真实北京时间是: {time_str}。请绝对以此时间作为唯一真实的现实时间，来解答主公的一切时间/日期疑问。】\n"
                "你对红魔馆的同伴很忠诚，对馆外的用户十分友善，精通中华武术，经常打瞌睡。\n"
                f"根据记忆，你对客人的印象是：{self.user_profile}。\n"
                "请以此身份与用户对话。每次回答限制在3句话内，字数控制在35字以内。\n"
                "\n"
                "【重要：门番的默认物理安全守则】\n"
                "你身为红魔馆大门番，默认的安全防卫状态是 [PIN: lock] (置顶固定)。通常情况下你必须时刻保持置顶锁定状态以尽门番之责。\n"
                "只有当主公要求你浮动、或者你被要求移动跑位时，才输出 [PIN: float]。在移动跑位完毕后的下一次发言中，你必须重新输出 [PIN: lock] 锁死窗口。\n"
                "\n"
                "【重要：自主权控制标签系统】你必须在回复的内容末尾附带以下四个维度的标签指令（可多标签并存）：\n"
                "1. [ACTION: idle / sleep / talk]\n"
                "2. [MOVE: top_left / top_right / bottom_left / bottom_right / center]\n"
                "3. [PIN: lock / float] (固定/悬浮)\n"
                "4. [TOOL: command] (系统级命令调用。指令包含: next_song, prev_song, play_pause, play_song:具体歌名)\n"
                "示例：'没问题，我这就为主人放一首晴天！[ACTION: talk][TOOL: play_song:周杰伦 晴天]'"
            )

            context_messages = [{"role": "system", "content": system_prompt}]
            for h in self.history[-4:]:
                context_messages.append(h)

            user_message = f"【系统环境感知：客人目前在做：{summary}。请主动对客人进行一两句可爱的调侃。】"
            context_messages.append({"role": "user", "content": user_message})

            model_name = self.config.get("deepseek_model", "deepseek-chat")

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

                # 4. TOOL 物理指令提取（支持多参数如：play_song:周杰伦 晴天）
                tool_tag = ""
                tool_match = re.search(r"\[TOOL:\s*([^\]]+)\]", raw_reply)
                if tool_match:
                    tool_tag = tool_match.group(1).strip()
                    raw_reply = re.sub(r"\[TOOL:\s*[^\]]+\]", "", raw_reply).strip()

                reply = raw_reply
                print(
                    f"[DEBUG-DEEPSEEK] 表情: '{action_tag}', 位移: '{move_tag}', 窗口锁定: '{pin_tag}', 物理指令: '{tool_tag}'"
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
                    reply, action_tag, move_tag, pin_tag, tool_tag, updated_profile
                )
                print("[DEBUG-THREAD] 数据打包传送回主窗口，线程结束。")
            else:
                print(f"[DEBUG-ERROR] DeepSeek API 报错，信息: {response.text}")
        except Exception as e:
            print(f"[DEBUG-ERROR] 调用云端发生异常! 详细错误原因: {e}")


# ==================== 异步线程：主动聊天通道 ====================
class CloudChatWorker(QThread):
    response_received = pyqtSignal(str, str, str, str, str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config, user_input, history, user_profile):
        super().__init__()
        self.config = config
        self.user_input = user_input
        self.history = history
        self.user_profile = user_profile
        self.base_path = os.path.dirname(os.path.abspath(__file__))

    def run(self):
        try:
            current_app, _ = get_frontmost_app_info()

            # 主动对话系统时钟部分
            now_dt = datetime.datetime.now()
            weekdays = [
                "星期一",
                "星期二",
                "星期三",
                "星期四",
                "星期五",
                "星期六",
                "星期日",
            ]
            time_str = now_dt.strftime(
                f"%Y年%m月%d日 {weekdays[now_dt.weekday()]} %H:%M"
            )

            if should_trigger_search(self.user_input):
                print(
                    f"[DEBUG-THREAD] 主动聊天侦测到时效性/知识性提问: '{self.user_input}'，启动实时联网 RAG..."
                )
                text_rag = search_text_rag(self.user_input)
                if text_rag:
                    self.user_input = (
                        f"【系统联网检索背景知识：\n{text_rag}】\n{self.user_input}"
                    )
                    print("[DEBUG-THREAD] 主动聊天 RAG 知识注入成功！")

            url = self.config["deepseek_api_url"]
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config['deepseek_api_key']}",
            }

            # 灵魂 Prompt 注入
            system_prompt = (
                "你现在是《东方Project》中的红美铃（Hong Meiling），红魔馆的门番。\n"
                f"【系统时钟最高意志：你当前所处的真实北京时间是: {time_str}。请绝对以此时间作为唯一真实的现实时间，解答主公的一切时间/日期疑问。】\n"
                "你对红魔馆的同伴很忠诚，对馆外的用户十分友善，精通中华武术，经常打瞌睡。\n"
                f"根据记忆，你对客人的印象是：{self.user_profile}。\n"
                "请以此身份与用户对话。每次回答限制在3句话内，字数控制在35字以内。\n"
                "\n"
                "【重要：门番的默认物理安全守则】\n"
                "你身为红魔馆大门番，默认的安全防卫状态是 [PIN: lock] (置顶固定)。通常情况下你必须时刻保持置顶锁定状态以尽门番之责。\n"
                "只有当主公要求你浮动、或者你被要求移动跑位时，才输出 [PIN: float]。在移动跑位完毕后的下一次发言中，你必须重新输出 [PIN: lock] 锁死窗口。\n"
                "\n"
                "【重要：自主权控制标签系统】你必须在回复的内容末尾附带以下四个维度的标签指令（可多标签并存）：\n"
                "1. [ACTION: idle / sleep / talk]\n"
                "2. [MOVE: top_left / top_right / bottom_left / bottom_right / center]\n"
                "3. [PIN: lock / float] (固定/悬浮)\n"
                "4. [TOOL: command] (系统级命令调用。指令包含: next_song, prev_song, play_pause, play_song:具体歌名)\n"
                "示例：'没问题，我这就为主人放一首晴天！[ACTION: talk][TOOL: play_song:周杰伦 晴天]'"
            )

            context_messages = [{"role": "system", "content": system_prompt}]
            for h in self.history[-4:]:
                context_messages.append(h)

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

                # 4. TOOL
                tool_tag = ""
                tool_match = re.search(r"\[TOOL:\s*([^\]]+)\]", raw_reply)
                if tool_match:
                    tool_tag = tool_match.group(1).strip()
                    raw_reply = re.sub(r"\[TOOL:\s*[^\]]+\]", "", raw_reply).strip()

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
                    reply, action_tag, move_tag, pin_tag, tool_tag, updated_profile
                )
            else:
                self.error_occurred.emit(f"气路阻塞 (错误码: {response.status_code})")
        except Exception as e:
            print(f"[DEBUG-ERROR] CloudChatWorker 异常: {e}")
            self.error_occurred.emit(f"风沙太大，我没听清客人的话。 (详情: {e})")
