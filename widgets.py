import os
import json
import re  # 修复：补充导入缺失的正则表达式标准库
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QTextBrowser,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QTextEdit,
)
from PyQt5.QtGui import QKeyEvent


# ==================== 古风自适应输入框 ====================
class GuofengTextEdit(QTextEdit):
    """支持回车发送、Shift+回车换行的国风文本输入框"""

    enterPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.enterPressed.emit()
        else:
            super().keyPressEvent(event)


# ==================== “红魔馆门番交往日志” 历史对话浏览器 ====================
class HistoryWindow(QDialog):
    """红美铃专属国风历史对话查询窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(300, 400)
        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 背景与外边框容器
        container = QLabel(self)
        container.setGeometry(0, 0, 300, 400)
        container.setStyleSheet("""
            QLabel {
                background-color: rgba(250, 246, 240, 0.98);
                border: 2px solid #9f1d1d;
                border-double-width: 6px;
                border-radius: 8px;
            }
        """)

        # 1. 窗口标题
        title_label = QLabel("红魔馆门番交往日志")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: #9f1d1d;
            font-family: "Kaiti SC", "STKaiti", "KaiTi", sans-serif;
            font-size: 14px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)

        # 2. 历史内容浏览器
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #faf6f0;
                border: 1px solid #b89150;
                border-radius: 4px;
                padding: 10px;
                color: #2c1010;
                font-family: "Kaiti SC", "STKaiti", "KaiTi", sans-serif;
                font-size: 12px;
                font-weight: bold;
                line-height: 150%;
            }
        """)

        # 3. 极简底部按钮
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("封存")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #9f1d1d;
                border: 1px solid #b89150;
                border-radius: 4px;
                color: #faf6f0;
                font-family: "Kaiti SC", "STKaiti", "KaiTi", sans-serif;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 15px;
            }
            QPushButton:hover { background-color: #c92a2a; }
        """)
        self.close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        btn_layout.addStretch()

        layout.addWidget(title_label)
        layout.addWidget(self.browser)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_history(self):
        """动态加载本地 memory.json 中存储的往来对话日志"""
        self.browser.clear()
        memory_file = "./memory.json"

        if not os.path.exists(memory_file):
            self.browser.append(
                "<p style='color: #b89150; text-align: center;'>（日志尚未开卷……）</p>"
            )
            return

        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                history = data.get("conversation_history", [])

            if not history:
                self.browser.append(
                    "<p style='color: #b89150; text-align: center;'>（今日尚无往来信件喵……）</p>"
                )
                return

            for msg in history:
                role = msg.get("role")
                content = msg.get("content", "").strip()

                # 过滤可能存在的系统前置环境敏感提示词，仅保留干净的对话
                if "【系统环境" in content or "【系统事件" in content:
                    # 正则提取真实的对话内容
                    clean_match = re.search(r"】\n(.*)", content, re.DOTALL)
                    if clean_match:
                        content = clean_match.group(1).strip()

                if not content:
                    continue

                if role == "user":
                    self.browser.append(
                        f"<span style='color:#b89150;'>主公：</span>{content}<br>"
                    )
                elif role == "assistant":
                    self.browser.append(
                        f"<span style='color:#9f1d1d;'>美铃：</span>{content}<br><br>"
                    )
        except Exception as e:
            self.browser.append(f"<p style='color: red;'>日志装载异常: {e}</p>")

    # 允许主公用鼠标拖动历史记录面板
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
