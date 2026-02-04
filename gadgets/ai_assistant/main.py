import sys
import os
import time
import ctypes
import io
import base64
from PIL import Image
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from gsf.gadget_base import BaseGadget
from openai import OpenAI

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_active_window_title():
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value
    
def capture_optimized_screen(max_size=(800, 800), quality=60):
    """
    截屏并进行有损压缩，大幅降低 Token 消耗
    """
    screen = QApplication.primaryScreen()
    if not screen: return None

    pixmap = screen.grabWindow(0)
    
    qimage = pixmap.toImage()
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    qimage.save(buffer, "PNG")
    pil_img = Image.open(io.BytesIO(buffer.data()))

    pil_img.thumbnail(max_size, Image.Resampling.LANCZOS)

    output_buffer = io.BytesIO()
    pil_img.save(output_buffer, format='JPEG', quality=quality) # quality=60 足够看清代码和视频内容
    
    return base64.b64encode(output_buffer.getvalue()).decode('utf-8')
    

class SettingsDialog(QDialog):
    def __init__(self, settings_path, parent=None):
        super().__init__(parent)
        self.settings_path = settings_path
        self.setWindowTitle("AI 配置")
        self.setFixedSize(320, 260)
        
        # 简单的暗色样式
        self.setStyleSheet("""
            QDialog { background-color: #333; color: #EEE; }
            QLabel { font-weight: bold; }
            QLineEdit { padding: 5px; border-radius: 4px; border: 1px solid #555; }
            QPushButton { background-color: #0078D7; color: white; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #198CE6; }
        """)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("API Base URL (可选, 默认 OpenAI):"))
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("例如: https://api.deepseek.com/v1")
        layout.addWidget(self.base_url)

        layout.addWidget(QLabel("API Key (必填):"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-...")
        layout.addWidget(self.api_key)

        layout.addWidget(QLabel("模型名称:"))
        self.model_name = QLineEdit()
        self.model_name.setPlaceholderText("gpt-4o-mini")
        self.model_name.setText("gpt-4o-mini") # 默认值
        layout.addWidget(self.model_name)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        self.load_settings()

    def load_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        self.base_url.setText(settings.value("ai/base_url", ""))
        self.api_key.setText(settings.value("ai/api_key", ""))
        self.model_name.setText(settings.value("ai/model_name", "gpt-4o-mini"))

    def save_settings(self):
        settings = QSettings(self.settings_path, QSettings.IniFormat)
        settings.setValue("ai/base_url", self.base_url.text().strip())
        settings.setValue("ai/api_key", self.api_key.text().strip())
        settings.setValue("ai/model_name", self.model_name.text().strip())
        self.accept()

class MonitorThread(QThread):
    context_changed = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.last_window_title = ""
        self.last_check_time = 0
        self.running = True

    def run(self):
        user32 = ctypes.windll.user32
        while self.running:
            try:
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                current_title = buff.value

                if current_title and current_title != self.last_window_title:
                    time.sleep(2)
                    
                    hwnd_check = user32.GetForegroundWindow()
                    length_check = user32.GetWindowTextLengthW(hwnd_check)
                    buff_check = ctypes.create_unicode_buffer(length_check + 1)
                    user32.GetWindowTextW(hwnd_check, buff_check, length_check + 1)
                    
                    if buff_check.value == current_title:
                        print(f"检测到环境切换: {current_title}，正在截图分析...")
                        
                        img_base64 = capture_optimized_screen() 
                        
                        app_type = "General"
                        if any(k in current_title for k in ["Code", "PyCharm", "Studio"]): app_type = "Coding"
                        elif "Bilibili" in current_title or "YouTube" in current_title: app_type = "Video"
                        
                        self.context_changed.emit(app_type, current_title, img_base64)
                        
                        self.last_window_title = current_title
                
            except Exception as e:
                print(f"Monitor error: {e}")
            
            time.sleep(1)

    def stop(self): self.running = False

class AIWorker(QThread):
    response_ready = Signal(str)

    def __init__(self, prompt, config, system_role="passive", image_data=None):
        super().__init__()
        self.prompt = prompt
        self.config = config
        self.system_role = system_role
        self.image_data = image_data

    def run(self):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url")
        if not base_url or base_url.strip() == "":
            base_url = None
            
        model = self.config.get("model")
        if not model or model.strip() == "":
            model = "gpt-4o-mini"

        if not api_key:
            self.response_ready.emit("⚠️ 还没有配置 API Key 哦！请右键点击我 -> 设置。")
            return

        try:
            is_vision_model = False
            if any(v in model for v in ["gpt-4o", "claude-3", "gemini", "qwen-vl", "lava"]):
                is_vision_model = True
            
            if "deepseek" in model:
                is_vision_model = False
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            if self.system_role == "passive":
                sys_msg = (
                    "你是一个住在用户屏幕角落的桌面宠物助手（类似 Clippy）。"
                    "用户正在操作电脑，我会发给你屏幕截图或文字描述。"
                    "请用简短（30字以内）、幽默、稍微有点毒舌或者贴心的语气点评用户的当前行为。"
                    "不要长篇大论，像个朋友一样随口吐槽一句即可。"
                )
            else:
                sys_msg = "你是一个乐于助人的桌面助手，回答要在简练的基础上保持准确。"

            messages = [{"role": "system", "content": sys_msg}]

            if self.image_data and is_vision_model:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{self.image_data}"
                            }
                        }
                    ]
                })
            else:
                final_prompt = self.prompt
                if self.image_data:
                    final_prompt += "\n\n(注：当前模型不支持视觉，已自动忽略截图数据，请仅根据文字描述进行回答。)"
                
                messages.append({"role": "user", "content": final_prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            content = response.choices[0].message.content
            self.response_ready.emit(content)

        except Exception as e:
            error_str = str(e)
            print(error_str)
            if "401" in error_str:
                self.response_ready.emit("API Key 好像不对 (401 Unauthorized)。")
            elif "404" in error_str:
                self.response_ready.emit(f"找不到模型 '{model}'，请检查设置。")
            else:
                self.response_ready.emit(f"脑子卡住了... ({error_str[:50]}...)")

class ClippyGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        self.gadget_path = gadget_path
        self.settings_file = os.path.join(self.gadget_path, 'config.ini')

        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint |
                            Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.resize(300, 150) 
        
        self.setup_ui()
        
        self.monitor = MonitorThread()
        self.monitor.context_changed.connect(self.on_user_activity_change)
        self.monitor.start()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setAlignment(Qt.AlignBottom | Qt.AlignRight)

        self.bubble = QLabel("右键点击我可以设置 API Key 哦！")
        self.bubble.setWordWrap(True)
        self.bubble.setVisible(True) # 初始显示提示
        self.bubble.setStyleSheet("background-color: #FFFFE0; color: #000; border: 1px solid #AAA; border-radius: 10px; padding: 10px; font-size: 12px;")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setOffset(2, 2)
        self.bubble.setGraphicsEffect(shadow)
        self.layout.addWidget(self.bubble)

        self.bubble_timer = QTimer()
        self.bubble_timer.setInterval(5000)
        self.bubble_timer.timeout.connect(lambda: self.bubble.setVisible(False))
        self.bubble_timer.start()

        self.avatar = QLabel("📎")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(120, 120)
        self.avatar.setStyleSheet("font-size: 40px; background: transparent;")
        self.avatar.setCursor(Qt.PointingHandCursor)
        
        img_path = os.path.join(self.gadget_path, "assets", "avatar.png")
        if os.path.exists(img_path):
            self.avatar.setText("")
            self.avatar.setPixmap(QPixmap(img_path).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        self.layout.addWidget(self.avatar, 0, Qt.AlignRight)

    def populate_context_menu(self, menu):
        """这是 BaseGadget 留给我们的接口，用于向右键菜单添加内容"""
        menu.addSeparator()
        
        setting_action = menu.addAction("⚙️ 设置 (Settings)...")
        setting_action.triggered.connect(self.open_settings)
        
        poke_action = menu.addAction("👈 戳一下 (Test)")
        poke_action.triggered.connect(lambda: self.trigger_ai("用户戳了你一下，给个反应。", "passive"))
        
    def open_settings(self):
        """打开配置窗口"""
        dialog = SettingsDialog(self.settings_file, self)
        if dialog.exec():
            self.show_bubble("配置已保存！正在尝试连接...", 3000)

    def on_user_activity_change(self, app_type, title, img_base64):
        prompt = ""
        if app_type == "Coding":
            prompt = f"我现在正在写代码，窗口标题是 '{title}'。请看看我的屏幕截图，如果有报错请指出来，如果没有，请根据代码内容给一句简短的建议或鼓励。"
        elif app_type == "Video":
            prompt = f"我正在看视频 '{title}'。看一眼截图，用幽默的语气吐槽一下画面里的内容。"
        else:
            prompt = f"我切换到了 '{title}'。看截图，简短评价一下我在干嘛。"

        self.show_bubble("👀 观察中...", duration=0) 
        self.trigger_ai(prompt, role="passive", image_data=img_base64)

    def mouseDoubleClickEvent(self, event):
        """双击本体，打开完整聊天窗口 (这里简化为弹出一个输入框)"""
        text, ok = QInputDialog.getText(self, "手动交流", "你想聊什么？")
        if ok and text:
            self.show_bubble("🤔 思考中...", duration=0)
            self.trigger_ai(text, role="active")

    def trigger_ai(self, text, role, image_data=None):
        settings = QSettings(self.settings_file, QSettings.IniFormat)
        config = {
            "api_key": settings.value("ai/api_key", ""),
            "base_url": settings.value("ai/base_url", ""),
            "model": settings.value("ai/model_name", ""),
        }
        
        self.worker = AIWorker(text, config, system_role=role, image_data=image_data)
        self.worker.response_ready.connect(lambda response: self.show_bubble(response, duration=8000))
        self.worker.start()

    def show_bubble(self, text, duration=5000):
        """显示气泡"""
        self.bubble.setText(text)
        self.bubble.setVisible(True)
        self.bubble.adjustSize()
        
        if duration > 0:
            self.bubble_timer.setInterval(duration)
            self.bubble_timer.start()
        else:
            self.bubble_timer.stop()

    def hide_bubble(self):
        self.bubble.setVisible(False)
        self.bubble_timer.stop()

    def paintEvent(self, event):
        pass

if __name__ == '__main__':
    gadget_path_arg = sys.argv[1]
    
    app = QApplication(sys.argv)
    gadget = ClippyGadget(gadget_path=gadget_path_arg)
    gadget.show()
    sys.exit(app.exec())