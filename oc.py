import sys
import os
import re
import time
import random
import json
import warnings  # 导入系统级警告过滤器

# 强行屏蔽 macOS 因系统 LibreSSL 产生的 urllib3 警告，保持控制台绝对整洁
warnings.filterwarnings("ignore", module="urllib3")
warnings.simplefilter("ignore", category=UserWarning)

from PyQt5.QtCore import (
    Qt,
    QPoint,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QHBoxLayout,
    QMenu,
    QGraphicsOpacityEffect,
    QPushButton,
)
from PyQt5.QtGui import QPixmap, QIcon

# 引入大脑模块以及新增的 HTTP 接收服务
from brain import (
    get_frontmost_app_info,
    LocalSensingWorker,
    CloudChatWorker,
    LocalServerThread,
)

# 引入古风自定义组件
from widgets import GuofengTextEdit, HistoryWindow


class MeilingPet(QWidget):
    def __init__(self):
        super().__init__()
        # 1. 变量和绝对路径初始化
        self.init_variables()
        self.load_config()
        self.load_memory_data()
        self.init_ui()

        # 2. 开机待机设定（直接初始化在睡觉姿态，不显示空白气泡）
        self.character_state = "sleeping"
        self.set_mascot_image(self.img_action4)

        # 3. 定时器与服务初始化
        self.init_timers()
        self.setup_autostart()

        # 4. 启动本地 10 秒开机待机呼吸文本动画（优雅向主公反馈后台加载进度，拒绝 443 报错）
        self.start_startup_standby_animation()

        # 5. 延迟开机主动问候时钟：动态读取外部延迟时间（默认10秒），转换为毫秒触发
        delay_ms = int(self.config.get("startup_delay_seconds", 10)) * 1000
        QTimer.singleShot(delay_ms, self.trigger_startup_greeting)

    def load_config(self):
        self.config_file = os.path.join(self.base_path, "config.json")
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = self.get_default_config()
        else:
            self.config = self.get_default_config()
            self.save_config()

    def get_default_config(self):
        return {
            "deepseek_api_key": "sk-xxxxxxxxxxxxxxxxxxx",
            "deepseek_api_url": "https://api.deepseek.com/chat/completions",
            "deepseek_model": "deepseek-chat",
            "ollama_api_url": "http://localhost:11434/api/generate",
            "ollama_model": "qwen2.5:1.5b",
            "idle_sleep_timeout_seconds": 120,
            "cooldown_seconds": 10,
            "startup_delay_seconds": 10,
            "windows_scale_factor": 1.3,
            "mac_scale_factor": 1.0,
            "debug_mode": True,
            "autostart": True,
            "startup_position": "bottom_right",
            "startup_commands": ["给红美铃喂茶点", "端起杯子多喝热水"],
        }

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def load_memory_data(self):
        self.memory_file = os.path.join(self.base_path, "memory.json")
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory_data = json.load(f)
            except Exception:
                self.memory_data = {
                    "user_profile": "红魔馆尊贵的客人",
                    "wake_up_count": 0,
                    "conversation_history": [],
                }
        else:
            self.memory_data = {
                "user_profile": "红魔馆尊贵的客人",
                "wake_up_count": 0,
                "conversation_history": [],
            }

    def save_memory_data(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory_data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def debug_print(self, msg):
        """调试日志输出控制台，支持在一键静音全局 [DEBUG] 信息"""
        if hasattr(self, "config") and self.config.get("debug_mode", True):
            print(msg)

    def purify_png_iccp(self, filepath):
        """物理净化器：在二进制流底层剥离 iCCP 数据块，绝对无损、安全"""
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "rb") as f:
                data = f.read()

            if data[:8] != b"\x89PNG\r\n\x1a\n":
                return

            import struct

            out = bytearray(data[:8])
            pos = 8
            modified = False

            while pos < len(data):
                length_bytes = data[pos : pos + 4]
                if len(length_bytes) < 4:
                    break
                length = struct.unpack(">I", length_bytes)[0]
                chunk_type = data[pos + 4 : pos + 8]

                if chunk_type == b"iCCP":
                    pos += 12 + length
                    modified = True
                    continue

                out.extend(data[pos : pos + 12 + length])
                pos += 12 + length

            if modified:
                with open(filepath, "wb") as f:
                    f.write(out)
                self.debug_print(
                    f"[DEBUG-IMAGE] 已成功在二进制层面净化并修复立绘配置文件: {filepath}"
                )
        except Exception as e:
            self.debug_print(f"[DEBUG-ERROR] 物理净化图片 {filepath} 失败: {e}")

    def init_variables(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.img_action1 = os.path.join(self.base_path, "action1.png")
        self.img_action2 = os.path.join(self.base_path, "action2.png")
        self.img_action3 = os.path.join(self.base_path, "action3.png")
        self.img_action4 = os.path.join(self.base_path, "action4.png")

        # 启动时自动扫描并对立绘图片进行物理贴图净化
        for img_path in [
            self.img_action1,
            self.img_action2,
            self.img_action3,
            self.img_action4,
        ]:
            self.purify_png_iccp(img_path)

        self.is_dragging = False
        self.is_pinned = True
        self.drag_start_pos = QPoint()
        self.drag_position = QPoint()

        self.sentences = []
        self.current_sentence_index = 0
        self.current_sentence_text = ""
        self.typed_char_count = 0

        # 脑体解耦双轨状态机设计
        self.dialogue_state = "idle"
        self.character_state = "idle"

        self.state_enter_time = 0
        self.last_interaction_time = time.time()
        self.temp_user_input = ""

        self.last_clipboard_text = ""
        self.last_comment_time = 0
        self.temp_unpin_needed = False

    def init_ui(self):
        self.setFixedSize(280, 360)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.bubble = QLabel(self)
        self.bubble.setGeometry(20, 10, 240, 85)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignCenter)
        self.bubble.setStyleSheet("""
            QLabel {
                background-color: rgba(250, 246, 240, 0.96);
                border: 4px double #9f1d1d;
                border-radius: 4px;
                padding: 6px 10px;
                color: #5c1212;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        self.bubble.installEventFilter(self)

        self.opacity_effect = QGraphicsOpacityEffect(self.bubble)
        self.bubble.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        self.bubble.hide()

        self.mascot = QLabel(self)
        self.mascot.setGeometry(50, 100, 180, 180)
        self.mascot.setAlignment(Qt.AlignCenter)
        self.mascot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.set_mascot_image(self.img_action1)

        # 底部自适应容器
        self.input_container = QWidget(self)
        self.input_container.setGeometry(15, 303, 250, 42)

        self.input_layout = QHBoxLayout(self.input_container)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(4)

        self.input_edit = GuofengTextEdit()
        self.input_edit.setPlaceholderText("唤醒或搭话...")
        self.input_edit.setFixedHeight(32)
        self.input_edit.document().setDocumentMargin(3)
        self.input_edit.setStyleSheet("""
            QTextEdit {
                background-color: #faf6f0;
                border: 1px solid #b89150;
                border-radius: 4px;
                padding: 2px 4px;
                color: #5c1212;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.input_edit.textChanged.connect(self.adjust_input_height)
        self.input_edit.enterPressed.connect(self.send_message)

        # 历史查询按钮
        self.hist_btn = QPushButton("历史")
        self.hist_btn.setFixedWidth(38)
        self.hist_btn.setFixedHeight(32)
        self.hist_btn.setStyleSheet("""
            QPushButton {
                background-color: #faf6f0;
                border: 1px solid #b89150;
                border-radius: 4px;
                color: #b89150;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #f5eedc; }
        """)
        self.hist_btn.clicked.connect(self.open_history_window)

        self.pin_btn = QPushButton("固定")
        self.pin_btn.setFixedWidth(42)
        self.pin_btn.setFixedHeight(32)
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #9f1d1d;
                border: 1px solid #b89150;
                border-radius: 4px;
                color: #faf6f0;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 0px;
            }
            QPushButton:hover { background-color: #c92a2a; }
        """)
        self.pin_btn.clicked.connect(self.toggle_pin)

        self.send_btn = QPushButton("递茶")
        self.send_btn.setFixedWidth(42)
        self.send_btn.setFixedHeight(32)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #faf6f0;
                border: 1px solid #9f1d1d;
                border-radius: 4px;
                color: #9f1d1d;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 0px;
            }
            QPushButton:hover { background-color: #fcece8; }
        """)
        self.send_btn.clicked.connect(self.send_message)

        self.input_layout.addWidget(self.input_edit)
        self.input_layout.addWidget(self.hist_btn)
        self.input_layout.addWidget(self.pin_btn)
        self.input_layout.addWidget(self.send_btn)

        # 核心：调用开机智能精准物理落位
        self.apply_startup_position()

    def init_timers(self):
        """初始化全局定时器、系统被动感知，以及 HTTP 本地服务器"""
        # 1. 逐字打印打字机时钟
        self.typewriter_timer = QTimer(self)
        self.typewriter_timer.timeout.connect(self.typewriter_tick)

        # 2. 说话口型起伏时钟
        self.mouth_timer = QTimer(self)
        self.mouth_timer.timeout.connect(self.toggle_mouth)
        self.mouth_is_open = False

        # 3. 状态机轮询时钟
        self.state_tick_timer = QTimer(self)
        self.state_tick_timer.timeout.connect(self.state_tick)
        self.state_tick_timer.start(100)

        # 4. 被动闲置自动休眠检测时钟
        self.env_monitor_timer = QTimer(self)
        self.env_monitor_timer.timeout.connect(self.monitor_environment_and_sleep)
        self.env_monitor_timer.start(10000)

        # 5. 挂载全局剪贴板信号监听
        QApplication.clipboard().dataChanged.connect(self.on_clipboard_changed)

        # 6. 开启本地 HTTP 服务器（18088 端口）接收 Chrome 插件发来的数据
        self.server_thread = LocalServerThread(18088)
        self.server_thread.web_content_received.connect(self.on_web_content_received)
        self.server_thread.start()

    # ==================== 开机 10 秒待机动效（呼吸效果） ====================
    def start_startup_standby_animation(self):
        """物理呼吸动效：在开机初始化网络延迟的10秒内，美铃保持action4酣睡，气泡进行有节律的Zzz跳动"""
        self.dialogue_state = "typing"  # 借用typing状态拦截气泡自动淡出
        self.bubble.show()
        self.opacity_effect.setOpacity(1.0)

        self.standby_step = 0
        self.startup_anim_timer = QTimer(self)
        self.startup_anim_timer.timeout.connect(self.startup_standby_tick)
        self.startup_anim_timer.start(1000)  # 每秒跳动一次
        self.startup_standby_tick()  # 立即激活首次渲染

    def startup_standby_tick(self):
        """呼吸文本循环生成器"""
        dots = "." * (self.standby_step % 4)
        snores = "z" * (self.standby_step % 3 + 1)
        text = f"（红魔馆门番睡眠中{dots} {snores.upper()}...）"
        self.bubble.setText(text)
        self.standby_step += 1

    # ==================== 开机自适应精准定位 ====================
    def apply_startup_position(self):
        """开机物理定位：根据 config.json 中的 startup_position，在启动第0秒无感知闪现落位"""
        try:
            screen = QApplication.primaryScreen().geometry()
            sw, sh = screen.width(), screen.height()

            offset_x, offset_y = 30, 50
            targets = {
                "top_left": (offset_x, offset_y),
                "top_right": (sw - self.width() - offset_x, offset_y),
                "bottom_left": (offset_x, sh - self.height() - offset_y),
                "bottom_right": (
                    sw - self.width() - offset_x,
                    sh - self.height() - offset_y,
                ),
                "center": ((sw - self.width()) // 2, (sh - self.height()) // 2),
            }

            pos_name = self.config.get("startup_position", "bottom_right")
            if pos_name in targets:
                # 修复：移除错误的未定义变量 corner_name，统一重构为自适应落位参数 pos_name
                tx, ty = targets[pos_name]
                self.move(tx, ty)
                self.debug_print(f"[DEBUG-SYSTEM] 已执行开机物理初始落位: '{pos_name}'")
        except Exception as e:
            self.debug_print(f"[DEBUG-ERROR] 开机物理初始落位失败: {e}")

    def setup_autostart(self):
        """双端自启动：直连 Python 解释器"""
        autostart_enabled = self.config.get("autostart", True)

        try:
            # 1. macOS 平台的自启动管理（已修复为独立的 if 块，避免 elif 缩进语法耦合）
            if sys.platform == "darwin":
                home = os.path.expanduser("~")
                plist_path = os.path.join(
                    home, "Library", "LaunchAgents", "com.meiling.pet.plist"
                )

                if autostart_enabled:
                    launch_agents_dir = os.path.join(home, "Library", "LaunchAgents")
                    if not os.path.exists(launch_agents_dir):
                        os.makedirs(launch_agents_dir)

                    local_python = os.path.join(
                        self.base_path, ".venv", "bin", "python"
                    )
                    python_executable = (
                        local_python
                        if os.path.exists(local_python)
                        else "/usr/bin/python3"
                    )
                    script_path = os.path.join(self.base_path, "oc.py")

                    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.meiling.pet</string>
    <key>WorkingDirectory</key>
    <string>{self.base_path}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_executable}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
                    with open(plist_path, "w", encoding="utf-8") as f:
                        f.write(plist_content)
                    self.debug_print("[DEBUG-SYSTEM] 已成功部署 macOS 开机自启动 plist")
                else:
                    if os.path.exists(plist_path):
                        os.remove(plist_path)
                        self.debug_print(
                            "[DEBUG-SYSTEM] 用户关闭了自启动，已自动清理 macOS 自启 plist 项"
                        )

            # 2. Windows 平台的自启动管理（独立的 if 块，已修正 os.path.join 拼写错误）
            if sys.platform == "win32":
                startup_dir = os.path.join(
                    os.getenv("APPDATA"),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                    "Startup",
                )
                target_bat = os.path.join(startup_dir, "meiling_startup.bat")

                if autostart_enabled:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    run_bat_path = os.path.join(current_dir, "run.bat")
                    if os.path.exists(run_bat_path):
                        with open(target_bat, "w", encoding="gbk") as f:
                            f.write(
                                f'@echo off\ncd /d "{current_dir}"\nstart "" "run.bat"\n'
                            )
                        self.debug_print(
                            "[DEBUG-SYSTEM] 已成功部署 Windows 开机自启动 bat"
                        )
                else:
                    if os.path.exists(target_bat):
                        os.remove(target_bat)
                        self.debug_print(
                            "[DEBUG-SYSTEM] 用户关闭了自启动，已自动清理 Windows 开机自启项"
                        )
        except Exception as e:
            self.debug_print(f"[DEBUG-ERROR] 配置自启动发生异常: {e}")

    def trigger_startup_greeting(self):
        """开机延时问候：关闭待机呼吸动画，唤醒美铃，并智能读取主公的开机备忘录进行自然提醒"""

        # 1. 安全注销并垃圾回收开机呼吸动画时钟
        if hasattr(self, "startup_anim_timer"):
            self.startup_anim_timer.stop()
            self.startup_anim_timer.deleteLater()

        # 2. 唤醒并重置美铃的脑体状态机为正常站立
        self.character_state = "idle"
        self.dialogue_state = "idle"
        self.set_mascot_image(self.img_action1)

        import datetime

        hour = datetime.datetime.now().hour

        # 3. 读取并拼接待办事项
        cmds = self.config.get("startup_commands", [])
        cmds_str = "、".join(cmds) if cmds else "无"

        greeting_trigger = (
            f"【系统事件：主公刚刚开机启动了电脑，当前时间是 {hour} 点。\n"
            f"另外，主公今天定下了以下开机备忘待办项：'{cmds_str}'。\n"
            f"请你主动向主公说一句符合当前时辰的、极其热情的问候。并且用红美铃特有的爽朗、带一丁点傲娇门番的语气，"
            f"在问候中聪明、自然、体贴地提醒主公今天需要做什么事情（不要生硬机械地罗列，要完全融入你对主公的日常问好中）。】"
        )

        self.worker = CloudChatWorker(
            self.config,
            greeting_trigger,
            self.memory_data["conversation_history"],
            self.memory_data["user_profile"],
        )
        self.worker.response_received.connect(self.on_api_success)
        self.worker.error_occurred.connect(self.on_api_error)
        self.worker.start()

    def on_clipboard_changed(self):
        if self.character_state == "sleeping":
            return

        text = QApplication.clipboard().text().strip()
        if not text or text == self.last_clipboard_text:
            return

        self.last_clipboard_text = text
        now = time.time()

        # 核心加固：读取 config 里的被动感知冷却 CD
        cooldown = self.config.get("cooldown_seconds", 10)
        if now - self.last_comment_time < cooldown:
            self.debug_print(f"[DEBUG-UI] 被 {cooldown} 秒冷却限制拦截！")
            return

        if len(text) > 120:
            return

        BLACKLIST_KEYWORDS = [
            "login",
            "signin",
            "bank",
            "checkout",
            "pay",
            "password",
            "wallet",
            "mail.google",
            "token",
            "key",
        ]
        if any(kw in text.lower() for kw in BLACKLIST_KEYWORDS):
            self.debug_print(
                "[DEBUG-UI] 本地拦截：剪贴板检测到敏感信息关键字，放弃触发。"
            )
            return

        if hasattr(self, "sensing_worker") and self.sensing_worker.isRunning():
            return

        self.last_comment_time = now

        self.sensing_worker = LocalSensingWorker(
            self.config,
            text,
            self.memory_data["conversation_history"],
            self.memory_data["user_profile"],
            source="clipboard",
        )
        self.sensing_worker.response_received.connect(self.on_api_success)
        self.sensing_worker.start()

    def on_web_content_received(self, title, content):
        if self.character_state == "sleeping":
            return

        now = time.time()
        # 冷却
        cooldown = self.config.get("cooldown_seconds", 10)
        if now - self.last_comment_time < cooldown:
            self.debug_print(f"[DEBUG-UI] 被 {cooldown} 秒冷却限制拦截！")
            return

        if len(content) > 800:
            content = content[:800]

        BLACKLIST_KEYWORDS = [
            "login",
            "signin",
            "bank",
            "checkout",
            "pay",
            "password",
            "wallet",
            "mail.google",
            "token",
            "key",
        ]
        if any(kw in content.lower() for kw in BLACKLIST_KEYWORDS) or any(
            kw in title.lower() for kw in BLACKLIST_KEYWORDS
        ):
            self.debug_print(
                "[DEBUG-UI] 本地拦截：网页检测到敏感信息关键字，放弃触发。"
            )
            return

        if hasattr(self, "sensing_worker") and self.sensing_worker.isRunning():
            return

        self.last_comment_time = now

        self.sensing_worker = LocalSensingWorker(
            self.config,
            content,
            self.memory_data["conversation_history"],
            self.memory_data["user_profile"],
            source="browser",
        )
        self.sensing_worker.response_received.connect(self.on_api_success)
        self.sensing_worker.start()

    def open_history_window(self):
        """打开/刷新历史往来对话日志面板"""
        self.last_interaction_time = time.time()
        self.hist_window = HistoryWindow(self)

        main_geo = self.geometry()
        self.hist_window.move(main_geo.x() - 310, main_geo.y())
        self.hist_window.show()

    def move_to_corner_command(self, corner_name):
        try:
            screen = QApplication.primaryScreen().geometry()
            sw, sh = screen.width(), screen.height()

            offset_x, offset_y = 30, 50
            targets = {
                "top_left": (offset_x, offset_y),
                "top_right": (sw - self.width() - offset_x, offset_y),
                "bottom_left": (offset_x, sh - self.height() - offset_y),
                "bottom_right": (
                    sw - self.width() - offset_x,
                    sh - self.height() - offset_y,
                ),
                "center": ((sw - self.width()) // 2, (sh - self.height()) // 2),
            }

            if corner_name in targets:
                tx, ty = targets[corner_name]

                self.temp_unpin_needed = self.is_pinned
                if self.temp_unpin_needed:
                    self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
                    if sys.platform == "darwin":
                        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, False)
                    self.show()

                self.pos_anim = QPropertyAnimation(self, b"pos")
                self.pos_anim.setDuration(1500)
                self.pos_anim.setStartValue(self.pos())
                self.pos_anim.setEndValue(QPoint(tx, ty))
                self.pos_anim.setEasingCurve(QEasingCurve.InOutQuad)

                self.pos_anim.finished.connect(self.on_movement_finished)
                self.pos_anim.start()
        except Exception as e:
            self.debug_print(f"[DEBUG-ERROR] 物理位置跑动失败: {e}")

    def on_movement_finished(self):
        if self.temp_unpin_needed:
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            if sys.platform == "darwin":
                self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            self.show()
            self.temp_unpin_needed = False

    def evade_active_window(self):
        app, bounds_str = get_frontmost_app_info()
        if not bounds_str:
            return

        try:
            screen = QApplication.primaryScreen().geometry()
            sw, sh = screen.width(), screen.height()

            parts = [int(p) for p in bounds_str.split(",")]
            wl, wt, wr, wb = parts[0], parts[1], parts[2], parts[3]
            w_cx = (wl + wr) / 2
            w_cy = (wt + wb) / 2

            offset_x, offset_y = 30, 50
            corners = {
                "top_left": (offset_x, offset_y),
                "top_right": (sw - self.width() - offset_x, offset_y),
                "bottom_left": (offset_x, sh - self.height() - offset_y),
                "bottom_right": (
                    sw - self.width() - offset_x,
                    sh - self.height() - offset_y,
                ),
            }

            best_corner = "bottom_right"
            max_dist = 0
            for name, (cx, cy) in corners.items():
                dist = (cx - w_cx) ** 2 + (cy - w_cy) ** 2
                if dist > max_dist:
                    max_dist = dist
                    best_corner = name

            tx, ty = corners[best_corner]
            self.animate_to_position(tx, ty)
        except Exception:
            pass

    def animate_to_position(self, target_x, target_y):
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(1200)
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(QPoint(target_x, target_y))
        self.pos_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.pos_anim.start()

    def adjust_input_height(self):
        doc_height = self.input_edit.document().size().height()
        new_height = int(min(70, max(32, doc_height + 4)))
        container_height = new_height + 10
        self.input_container.setGeometry(
            15, 345 - container_height, 250, container_height
        )
        self.input_edit.setFixedHeight(new_height)

    def set_pinned_state(self, pin_state: bool):
        if self.is_pinned != pin_state:
            self.is_pinned = pin_state
            self.apply_pin_ui_and_flags()

    def toggle_pin(self):
        self.set_pinned_state(not self.is_pinned)

    def apply_pin_ui_and_flags(self):
        current_pos = self.pos()
        if self.is_pinned:
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            if sys.platform == "darwin":
                self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
            self.pin_btn.setText("固定")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #9f1d1d;
                    border: 1px solid #b89150;
                    border-radius: 4px;
                    color: #faf6f0;
                    font-family: "Kaiti SC", "STKaiti", sans-serif;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 0px;
                }
                QPushButton:hover { background-color: #c92a2a; }
            """)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
            if sys.platform == "darwin":
                self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, False)
            self.pin_btn.setText("浮动")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #faf6f0;
                    border: 1px solid #b89150;
                    border-radius: 4px;
                    color: #9f1d1d;
                    font-family: "Kaiti SC", "STKaiti", sans-serif;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 0px;
                }
                QPushButton:hover { background-color: #f5eedc; }
            """)
        self.move(current_pos)
        self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos()
            if not self.is_pinned:
                self.is_dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                self.set_mascot_image(self.img_action3)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            if self.character_state == "sleeping":
                self.set_mascot_image(self.img_action4)
            else:
                self.set_mascot_image(self.img_action1)

            if (event.globalPos() - self.drag_start_pos).manhattanLength() < 5:
                self.last_interaction_time = time.time()
                if self.character_state == "sleeping":
                    self.wake_up_meiling()
                else:
                    self.trigger_touch_response()
            event.accept()

    def set_mascot_image(self, path):
        if os.path.exists(path):
            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(
                180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.mascot.setPixmap(scaled_pixmap)
        else:
            self.mascot.setText("贴图丢失")
            self.mascot.setStyleSheet(
                "color: #9f1d1d; font-family: 'Kaiti SC'; font-size: 11px;"
            )

    def toggle_mouth(self):
        """控制说话嘴部起伏：说话绝对不会打断酣睡状态"""
        if (
            self.dialogue_state == "typing"
            and self.character_state != "sleeping"
            and not self.is_dragging
        ):
            if self.mouth_is_open:
                self.set_mascot_image(self.img_action1)
                self.mouth_is_open = False
            else:
                self.set_mascot_image(self.img_action2)
                self.mouth_is_open = True

    def monitor_environment_and_sleep(self):
        """核心重构：彻底安全地进行休眠检测"""
        now = time.time()
        if self.character_state == "sleeping":
            return

        timeout = self.config.get("idle_sleep_timeout_seconds", 120)
        if now - self.last_interaction_time > timeout:
            self.go_to_sleep()

    def go_to_sleep(self):
        self.character_state = "sleeping"
        self.set_mascot_image(self.img_action4)
        self.show_dialogue_list(["（美铃倚着长枪打起大顿来…… 呼……）"])
        self.evade_active_window()

    def wake_up_meiling(self):
        self.character_state = "idle"
        self.memory_data["wake_up_count"] += 1
        self.save_memory_data()
        responses = [
            "哇啊！咲夜小姐！我没有偷懒！……呼，原来是客人您啊，吓死我了……",
            "呼啊！……哈！看招！啊，是客人。刚才我那是在闭目行气，绝对没有睡着哦！",
            "呜呃……红魔馆大门一切正常！……那个，客人，请千万不要把这件事告诉咲夜小姐哦~",
        ]
        self.show_dialogue_list(self.parse_sentences(random.choice(responses)))

    def trigger_touch_response(self):
        responses = [
            "客人在欣赏我的这套拳路吗？",
            "需要进馆拜访吗？请等我为您通报。",
            "守护红魔馆是我的职责，主公的安全也包在身上！",
            "呼……吸…… 练武之人，调息最是重要。",
        ]
        self.show_dialogue_list(self.parse_sentences(random.choice(responses)))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFDFD;
                border: 1px solid #9f1d1d;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 22px;
                color: #9f1d1d;
                font-family: "Kaiti SC", "STKaiti", sans-serif;
                font-size: 11px;
                font-weight: bold;
            }
            QMenu::item:selected {
                background-color: #9f1d1d;
                color: white;
                border-radius: 2px;
            }
        """)

        feed_action = menu.addAction("送中华甜点")
        care_action = menu.addAction("红魔馆例行巡逻")
        status_action = menu.addAction("红美铃状态记录")
        exit_action = menu.addAction("让美铃去守门")

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == feed_action:
            self.feed_meiling()
        elif action == care_action:
            self.daily_care()
        elif action == status_action:
            self.show_status()
        elif action == exit_action:
            self.save_memory_data()
            if hasattr(self, "server_thread"):
                self.server_thread.stop()
                self.server_thread.wait()
            QApplication.quit()

    def feed_meiling(self):
        self.last_interaction_time = time.time()
        responses = [
            "哇，是乌龙茶和天津甘栗！多谢客人，值班顿时不困了！",
            "唔！这个豆沙包甜度正好，客人的手艺真棒！",
        ]
        self.show_dialogue_list(random.choice(responses).split(" "))

    def daily_care(self):
        self.last_interaction_time = time.time()
        self.show_dialogue_list(
            ["气流平静，红魔馆门前安全无虞！", "主公请安心工作，宵小之辈休想跨过此门。"]
        )

    def show_status(self):
        status_str = (
            f"守护者：红美铃\n"
            f"印象：{self.memory_data['user_profile']}\n"
            f"唤醒次数：{self.memory_data['wake_up_count']}次"
        )
        self.show_dialogue_list([status_str])

    def parse_sentences(self, text):
        parts = re.split(r"([，。！？\n])", text)
        sentences = []
        current = ""
        for p in parts:
            if not p:
                continue
            if p in ["，", "。", "！", "？", "\n"]:
                current += p
                sentences.append(current.strip())
                current = ""
            else:
                if current:
                    sentences.append(current.strip())
                current = p
        if current:
            sentences.append(current.strip())
        return [s for s in sentences if s]

    def show_dialogue_list(self, text_list):
        if not text_list:
            return
        self.sentences = text_list
        self.current_sentence_index = 0
        self.start_sentence()

    def start_sentence(self):
        self.current_sentence_text = self.sentences[self.current_sentence_index]
        self.typed_char_count = 0
        self.dialogue_state = "typing"
        self.state_enter_time = time.time()

        self.fade_in_bubble()
        self.typewriter_timer.start(80)
        self.mouth_timer.start(180)

    def typewriter_tick(self):
        if self.typed_char_count < len(self.current_sentence_text):
            self.typed_char_count += 1
            self.bubble.setText(self.current_sentence_text[: self.typed_char_count])
        else:
            self.finish_sentence()

    def finish_sentence(self):
        self.typewriter_timer.stop()
        self.mouth_timer.stop()

        if self.is_dragging:
            self.set_mascot_image(self.img_action3)
        elif self.character_state == "sleeping":
            self.set_mascot_image(self.img_action4)
        else:
            self.set_mascot_image(self.img_action1)

        self.bubble.setText(self.current_sentence_text)
        self.state_enter_time = time.time()

        if self.current_sentence_index < len(self.sentences) - 1:
            self.dialogue_state = "waiting_next"
        else:
            self.dialogue_state = "waiting_end"

    def bubble_clicked(self):
        now = time.time()
        if self.dialogue_state == "typing":
            self.finish_sentence()
        elif self.dialogue_state == "waiting_next":
            if now - self.state_enter_time >= 0.5:
                self.next_sentence()
        elif self.dialogue_state == "waiting_end":
            if now - self.state_enter_time >= 0.5:
                if self.character_state != "sleeping":
                    self.dialogue_state = "idle"
                self.fade_out_bubble()

    def next_sentence(self):
        self.current_sentence_index += 1
        self.start_sentence()

    def state_tick(self):
        now = time.time()
        if self.dialogue_state == "waiting_next":
            if now - self.state_enter_time >= 2.0:
                self.next_sentence()
        elif self.dialogue_state == "waiting_end":
            if now - self.state_enter_time >= 3.0:
                if self.character_state != "sleeping":
                    self.dialogue_state = "idle"
                self.fade_out_bubble()

    def eventFilter(self, obj, event):
        if obj == self.bubble and event.type() == event.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.bubble_clicked()
                return True
        return super().eventFilter(obj, event)

    def fade_in_bubble(self):
        self.bubble.show()
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

    def fade_out_bubble(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(400)
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(
            lambda: self.bubble.hide() if self.character_state != "sleeping" else None
        )
        self.anim.start()

    def send_message(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        if hasattr(self, "chat_worker") and self.chat_worker.isRunning():
            return

        text_lower = text.lower()
        if any(
            kw in text_lower
            for kw in [
                "浮动",
                "悬浮",
                "解开",
                "解密",
                "解除固定",
                "解开置顶",
                "解开固定",
                "解锁",
            ]
        ):
            self.set_pinned_state(False)
            self.debug_print("[DEBUG-LOCAL] 侦测到物理浮动指令，本地直接无感知解锁")
        elif any(kw in text_lower for kw in ["固定", "置顶", "别动", "锁死", "定身"]):
            self.set_pinned_state(True)
            self.debug_print("[DEBUG-LOCAL] 侦测到物理固定指令，本地直接无感知锁定置顶")

        # ==================== 智能开机配置拦截写入 ====================
        if any(w in text_lower for w in ["开机", "启动", "以后都"]):
            matched_pos = None
            if "左下" in text_lower:
                matched_pos = "bottom_left"
            elif "右下" in text_lower:
                matched_pos = "bottom_right"
            elif "左上" in text_lower:
                matched_pos = "top_left"
            elif "右上" in text_lower:
                matched_pos = "top_right"
            elif "中间" in text_lower or "中央" in text_lower:
                matched_pos = "center"

            if matched_pos:
                self.config["startup_position"] = matched_pos
                self.save_config()  # 永久写入保存 config.json
                self.debug_print(
                    f"[DEBUG-SYSTEM] 已无感更新 config 中的开机落位为: '{matched_pos}'"
                )
        # =============================================================

        self.temp_user_input = text
        self.input_edit.clear()
        self.adjust_input_height()

        self.last_interaction_time = time.time()

        if self.character_state == "sleeping":
            self.character_state = "idle"
            self.set_mascot_image(self.img_action1)

        self.show_dialogue_list(["（美铃正在凝气调息……）"])
        self.send_btn.setEnabled(False)

        self.chat_worker = CloudChatWorker(
            self.config,
            text,
            self.memory_data["conversation_history"],
            self.memory_data["user_profile"],
        )
        self.chat_worker.response_received.connect(self.on_api_success)
        self.chat_worker.error_occurred.connect(self.on_api_error)
        self.chat_worker.start()

    # ==================== 大脑回调处理 ====================
    def on_api_success(self, reply, emotion_action, move_tag, pin_tag, updated_profile):
        self.send_btn.setEnabled(True)

        # 1. 物理姿态重置与同步
        if emotion_action == "sleep":
            self.character_state = "sleeping"
            self.set_mascot_image(self.img_action4)
            self.evade_active_window()
        elif emotion_action == "talk":
            self.character_state = "idle"
            self.set_mascot_image(self.img_action1)
        else:
            self.character_state = "idle"
            self.set_mascot_image(self.img_action1)

        # 2. 解析设置物理置顶/浮动状态
        if pin_tag == "lock":
            self.set_pinned_state(True)
            print("[DEBUG-AI] 红美铃决定自我视窗锁定")
        elif pin_tag == "float":
            self.set_pinned_state(False)
            print("[DEBUG-AI] 红美铃决定解除视窗锁定")

        # 3. 解析跑动物理位移指令
        if move_tag:
            self.move_to_corner_command(move_tag)

        self.memory_data["user_profile"] = updated_profile
        self.memory_data["conversation_history"].append(
            {"role": "user", "content": self.temp_user_input}
        )
        self.memory_data["conversation_history"].append(
            {"role": "assistant", "content": reply}
        )

        if len(self.memory_data["conversation_history"]) > 12:
            self.memory_data["conversation_history"] = self.memory_data[
                "conversation_history"
            ][-12:]
        self.save_memory_data()

        parsed = self.parse_sentences(reply)
        self.show_dialogue_list(parsed)

    def on_api_error(self, error_msg):
        self.send_btn.setEnabled(True)
        # 如果是开机拥堵或日常网络波动，气泡会友好地展现错误，不再直接卡死
        self.show_dialogue_list([error_msg])


if __name__ == "__main__":
    # ==================== 独立极简读取 config.json，解耦 Qt 物理缩放因子时序 ====================
    scale_factor = "1.0"
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if sys.platform == "win32":
                    scale_factor = str(cfg.get("windows_scale_factor", 1.3))
                elif sys.platform == "darwin":
                    scale_factor = str(cfg.get("mac_scale_factor", 1.0))
        except Exception:
            pass

    # 1. 一键等比例全局无损放大
    os.environ["QT_SCALE_FACTOR"] = scale_factor

    # 2. 自动处理高分屏字形发虚问题
    if sys.platform == "win32" or sys.platform == "darwin":
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # ====================================================================

    app = QApplication(sys.argv)  # 确保系统环境变量设置位于 app 实例化之前！

    if os.path.exists(os.path.join(base_path, "action1.png")):
        app.setWindowIcon(QIcon(os.path.join(base_path, "action1.png")))

    pet = MeilingPet()
    pet.show()
    sys.exit(app.exec_())
