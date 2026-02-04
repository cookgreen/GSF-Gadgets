import sys
import os
import time
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

# 尝试导入你的基础类
try:
    from gsf.gadget_base import BaseGadget
except ImportError:
    # 仅用于无环境测试
    from base_gadget import BaseGadget

# --- 配置对话框类 ---
class SettingsDialog(QDialog):
    def __init__(self, settings_path, parent=None):
        super().__init__(parent)
        self.settings_path = settings_path
        self.setWindowTitle("AI Configuration")
        self.setFixedSize(300, 250)
        
        # 加载样式
        self.setStyleSheet("""
            QDialog { background-color: #2D2D30; color: #EEE; }
            QLabel { color: #BBB; font-size: 12px; }
            QLineEdit { 
                background-color: #3E3E42; border: 1px solid #555; 
                color: #FFF; padding: 4px; border-radius: 4px;
            }
            QPushButton {
                background-color: #0078D7; color: white; border: none;
                padding: 6px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #198CE6; }
        """)

        layout = QVBoxLayout(self)

        # 1. 模型提供商/Base URL
        layout.addWidget(QLabel("API Base URL (Optional/Ollama):"))
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        layout.addWidget(self.base_url_edit)

        # 2. API Key
        layout.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password) # 隐藏密钥
        self.api_key_edit.setPlaceholderText("sk-...")
        layout.addWidget(self.api_key_edit)

        # 3. Model Name
        layout.addWidget(QLabel("Model Name:"))
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("gpt-3.5-turbo")
        layout.addWidget(self.model_name_edit)

        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #555;")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.load_settings()

    def load_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        self.base_url_edit.setText(settings.value("ai/base_url", ""))
        self.api_key_edit.setText(settings.value("ai/api_key", ""))
        self.model_name_edit.setText(settings.value("ai/model_name", "gpt-3.5-turbo"))

    def save_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        settings.setValue("ai/base_url", self.base_url_edit.text().strip())
        settings.setValue("ai/api_key", self.api_key_edit.text().strip())
        settings.setValue("ai/model_name", self.model_name_edit.text().strip())
        self.accept()

# --- AI 逻辑工作线程 ---
class LLMWorker(QThread):
    chunk_received = Signal(str)
    finished = Signal()

    def __init__(self, user_prompt, config):
        super().__init__()
        self.user_prompt = user_prompt
        self.config = config # 包含 key, url, model

    def run(self):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url")
        model = self.config.get("model_name", "gpt-3.5-turbo")
        
        # 模拟调用逻辑 (此处接入实际的 requests 或 openai 库)
        try:
            if not api_key:
                self.chunk_received.emit("⚠️ 请先点击右上角设置按钮配置 API Key。")
                self.finished.emit()
                return

            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url)
            
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": self.user_prompt}],
                    stream=True,
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        self.chunk_received.emit(chunk.choices[0].delta.content)
                        
            except Exception as e:
                self.chunk_received.emit(f"Error: {e}")
                
            self.finished.emit()
            
        except Exception as e:
            self.chunk_received.emit(f"\n[Error: {str(e)}]")
        
        self.finished.emit()

# --- 主 Gadget 类 ---
class AIGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        
        self.gadget_path = gadget_path
        # 复用 BaseGadget 定义的 config.ini 路径
        self.settings_file = os.path.join(self.gadget_path, 'config.ini')

        self.resize(320, 480)
        self.setWindowTitle('AI Assistant')
        
        self.setup_ui()
        self.apply_styles()
        
        self.worker = None

    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- 顶部工具栏 (新增) ---
        top_bar = QHBoxLayout()
        
        title_label = QLabel("🤖 AI Chat")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        self.config_btn = QPushButton("⚙️")
        self.config_btn.setFixedSize(30, 30)
        self.config_btn.setToolTip("配置 API Key")
        self.config_btn.setCursor(Qt.PointingHandCursor)
        self.config_btn.clicked.connect(self.open_settings) # 连接槽函数

        top_bar.addWidget(title_label)
        top_bar.addStretch()
        top_bar.addWidget(self.config_btn)
        
        main_layout.addLayout(top_bar)

        # --- 聊天显示区 ---
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        main_layout.addWidget(self.chat_display)

        # --- 输入区 ---
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit()
        self.input_field.setFixedHeight(45)
        self.input_field.setPlaceholderText("Ask me anything...")
        self.input_field.installEventFilter(self)
        
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(45, 45)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

    def apply_styles(self):
        # 保持与之前类似的透明玻璃风格，增加顶部按钮样式
        self.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(0, 0, 0, 80);
                border: none; border-radius: 8px; color: #EEE;
                font-family: 'Segoe UI'; font-size: 13px; padding: 8px;
            }
            QTextEdit {
                background-color: rgba(255, 255, 255, 30);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 8px; color: #FFF;
                font-family: 'Segoe UI'; font-size: 13px; padding: 4px;
            }
            QTextEdit:focus { border: 1px solid #00AAFF; }
            /* 发送按钮 */
            QPushButton {
                background-color: #0078D7; border: none; border-radius: 8px;
                color: white; font-weight: bold;
            }
            QPushButton:hover { background-color: #198CE6; }
            /* 设置按钮特殊样式 */
            QPushButton[text="⚙️"] {
                background-color: rgba(255, 255, 255, 20);
                font-size: 16px;
            }
            QPushButton[text="⚙️"]:hover {
                background-color: rgba(255, 255, 255, 50);
            }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { 
                background: rgba(255,255,255,60); border-radius: 3px; 
            }
        """)

    def paintEvent(self, event):
        # 绘制半透明圆角背景
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor(20, 20, 30, 230)
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 16, 16)

    def open_settings(self):
        """打开配置窗口"""
        dialog = SettingsDialog(self.settings_file, self)
        # 模态对话框，阻塞主窗口直到关闭
        dialog.exec()

    def eventFilter(self, obj, event):
        if obj == self.input_field and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        # 获取当前配置
        settings = QSettings(self.settings_file, QSettings.IniFormat)
        config = {
            "api_key": settings.value("ai/api_key", ""),
            "base_url": settings.value("ai/base_url", ""),
            "model_name": settings.value("ai/model_name", "gpt-3.5-turbo")
        }

        self.append_chat("<b>You:</b> " + text, color="#4CC2FF")
        self.input_field.clear()
        self.input_field.setDisabled(True)

        self.append_chat("<b>AI:</b> ", color="#00E0A0", new_block=False)
        
        # 启动线程
        self.worker = LLMWorker(text, config)
        self.worker.chunk_received.connect(self.update_stream)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.start()

    def append_chat(self, html, color="#FFF", new_block=True):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        if new_block and self.chat_display.toPlainText() != "":
            html = "<br>" + html
        cursor.insertHtml(f"<span style='color:{color};'>{html}</span>" + ("<br>" if new_block else ""))
        self.chat_display.setTextCursor(cursor)

    def update_stream(self, chunk):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        chunk_html = chunk.replace("\n", "<br>")
        cursor.insertHtml(f"<span style='color:#EEE;'>{chunk_html}</span>")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def on_generation_finished(self):
        self.input_field.setDisabled(False)
        self.input_field.setFocus()
        self.append_chat("<br>", new_block=False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gadget = AIGadget(gadget_path=".")
    gadget.show()
    sys.exit(app.exec())