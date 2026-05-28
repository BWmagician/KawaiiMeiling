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
    pyqtSignal,
)

#  QtWidgets 导入中已包含 QPushButton 声明
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QHBoxLayout,
    QMenu,
    QGraphicsOpacityEffect,
    QPushButton,
)
from PyQt5.QtGui import QPixmap, QCursor, QKeyEvent, QIcon

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
        self.load_config()
        self.load_memory_data()
        self.init_variables()
        self.init_ui()
        self.init_timers()
        self.setup_autostart()
        self.trigger_startup_greeting()

    def load_config(self):
        self.config_file = "./config.json"
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
        }

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def load_memory_data(self):
        self.memory_file = "./memory.json"
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

    def init_variables(self):
        self.img_action1 = "./action1.png"
        self.img_action2 = "./action2.png"
        self.img_action3 = "./action3.png"
        self.img_action4 = "./action4.png"

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
        self.last_interaction_time = time.time()  # 记录主动交互的时间戳
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
            }
            QPushButton:hover { background-color: #fcece8; }
        """)
        self.send_btn.clicked.connect(self.send_message)

        self.input_layout.addWidget(self.input_edit)
        self.input_layout.addWidget(self.hist_btn)
        self.input_layout.addWidget(self.pin_btn)
        self.input_layout.addWidget(self.send_btn)

    def init_timers(self):
        self.typewriter_timer = QTimer(self)
        self.typewriter_timer.timeout.connect(self.typewriter_tick)

        self.mouth_timer = QTimer(self)
        self.mouth_timer.timeout.connect(self.toggle_mouth)
        self.mouth_is_open = False

        self.state_tick_timer = QTimer(self)
        self.state_tick_timer.timeout.connect(self.state_tick)
        self.state_tick_timer.start(100)

        self.env_monitor_timer = QTimer(self)
        self.env_monitor_timer.timeout.connect(self.monitor_environment_and_sleep)
        self.env_monitor_timer.start(10000)

        QApplication.clipboard().dataChanged.connect(self.on_clipboard_changed)

        self.server_thread = LocalServerThread(18088)
        self.server_thread.web_content_received.connect(self.on_web_content_received)
        self.server_thread.start()

    def closeEvent(self, event):
        self.save_memory_data()
        if hasattr(self, "server_thread"):
            self.server_thread.stop()
            self.server_thread.wait()
        event.accept()

    def setup_autostart(self):
        """双端自启动"""
        try:
            if sys.platform == "darwin":
                home = os.path.expanduser("~")
                launch_agents_dir = os.path.join(home, "Library", "LaunchAgents")
                if not os.path.exists(launch_agents_dir):
                    os.makedirs(launch_agents_dir)
                plist_path = os.path.join(launch_agents_dir, "com.meiling.pet.plist")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(current_dir, "run.sh")
                if os.path.exists(script_path):
                    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.meiling.pet</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
                    with open(plist_path, "w", encoding="utf-8") as f:
                        f.write(plist_content)

            elif sys.platform == "win32":
                startup_dir = os.path.join(
                    os.getenv("APPDATA"),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                    "Startup",
                )
                current_dir = os.path.dirname(os.path.abspath(__file__))
                run_bat_path = os.path.join(current_dir, "run.bat")
                if os.path.exists(run_bat_path):
                    target_bat = os.path.join(startup_dir, "meiling_startup.bat")
                    with open(target_bat, "w", encoding="gbk") as f:
                        f.write(
                            f'@echo off\ncd /d "{current_dir}"\nstart "" "run.bat"\n'
                        )
        except Exception:
            pass

    def trigger_startup_greeting(self):
        import datetime

        hour = datetime.datetime.now().hour
        greeting_trigger = f"【系统事件：主公刚刚开机启动了电脑，当前时间是{hour}点，请主动向主公说一句问安。】"

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
        if now - self.last_comment_time < 10:
            return

        if len(text) > 120:
            return

        # Python 本地 0 毫秒隐私和安全硬过滤
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
            print("[DEBUG-UI] 本地拦截：剪贴板检测到敏感信息关键字，放弃触发。")
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
        if now - self.last_comment_time < 10:
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
            print("[DEBUG-UI] 本地拦截：网页检测到敏感信息关键字，放弃触发。")
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
            print(f"[DEBUG-ERROR] 物理位置跑动失败: {e}")

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
            "守护红魔馆是我的职责，主公的安全也包身上！",
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
            print("[DEBUG-LOCAL] 侦测到物理浮动指令，本地直接无感知解锁")
        elif any(kw in text_lower for kw in ["固定", "置顶", "别动", "锁死", "定身"]):
            self.set_pinned_state(True)
            print("[DEBUG-LOCAL] 侦测到物理固定指令，本地直接无感知锁定置顶")

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
        self.show_dialogue_list([error_msg])


if __name__ == "__main__":
    # ==================== Windows 专属一键无损整体放大（必须在 app 实例化之前设置！） ====================
    if sys.platform == "win32":
        # 1. 一键等比例全局无损放大（1.3 表示放大 1.3 倍，可按需修改为 1.4, 1.5, 1.6 等）
        os.environ["QT_SCALE_FACTOR"] = "1.3"

        # 2. 自动处理高分屏字形发虚问题
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # ====================================================================

    app = QApplication(sys.argv)  # 确保系统环境变量设置位于 app 实例化之前！

    if os.path.exists("./action1.png"):
        app.setWindowIcon(QIcon("./action1.png"))

    pet = MeilingPet()
    pet.show()
    sys.exit(app.exec_())
