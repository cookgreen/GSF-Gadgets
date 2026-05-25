import sys
import os
import random
import numpy as np
from typing import Optional, Callable, Tuple, Any
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from gsf.gadget_base import BaseGadget

from radio_browser_api import *
from radio_player import *

AUDIO_FORMAT = "S16N"
CHANNELS = 2
RATE = 44100

class CircularFavicon(QWidget):
    def __init__(self, size=150, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.image_size = size
        
        # 默认占位图（比如你截图里的声波图片）
        self.current_pixmap = QPixmap(size, size)
        self.current_pixmap.fill(QColor("#2C2C2C")) # 默认深灰色背景
        
        # 添加图片中那种淡淡的阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

        # 用于异步下载图片的网络管理器
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._on_image_downloaded)

    def load_from_url(self, url_str: str):
        """传入 API 中的 favicon URL 进行加载"""
        if not url_str:
            return
        request = QNetworkRequest(QUrl(url_str))
        self.network_manager.get(request)

    def _on_image_downloaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            img_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(img_data):
                # 将下载的图片缩放到我们控件的尺寸，保持比例，裁剪多余部分
                self.current_pixmap = pixmap.scaled(
                    self.image_size, self.image_size, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.update() # 触发 paintEvent 重绘
        reply.deleteLater()

    def paintEvent(self, event):
        """核心：将矩形图片裁剪为圆形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 创建一个圆形的裁剪路径
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        
        # 应用裁剪路径
        painter.setClipPath(path)
        
        # 居中绘制图片
        x_offset = (self.width() - self.current_pixmap.width()) // 2
        y_offset = (self.height() - self.current_pixmap.height()) // 2
        painter.drawPixmap(x_offset, y_offset, self.current_pixmap)

class InitializationWorker(QObject):
    status_updated = Signal(str) 
    initialization_finished = Signal()

    def __init__(self, api: RadioBrowserApi):
        super().__init__()
        self.api = api
    
    @Slot()
    def run(self):
        self.status_updated.emit("Initializing the data...")
        self.api.read_data_all()
        
        while True:
            if len(self.api.radio_data) > 0:
                break
            time.sleep(0.1)
                
        self.status_updated.emit("Initialization Completed")
        
        time.sleep(1)
        
        self.initialization_finished.emit()

class QImageButton(QWidget):
    clicked = Signal() # 添加点击信号

    def __init__(self, size: tuple[int, int],
                 normal_pixmap: QPixmap,
                 hover_pixmap: QPixmap,
                 disabled_pixmap: QPixmap,
                 callback=None, parent=None):
        super().__init__(parent)
        # 不再需要传入 pos，Layout 会自动安排位置！
        self.setFixedSize(size[0], size[1])
        
        self.normal_pixmap = normal_pixmap
        self.hover_pixmap = hover_pixmap
        self.disabled_pixmap = disabled_pixmap
        self.callback = callback
        
        self.hovered = False
        self._is_enabled = True 
        self.setMouseTracking(True) # 开启鼠标追踪

    def setEnabled(self, enabled: bool):
        self._is_enabled = enabled
        self.update()

    def enterEvent(self, event):
        if self._is_enabled:
            self.hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._is_enabled:
            self.hovered = False
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_enabled:
            if self.callback:
                self.callback()
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        if not self._is_enabled:
            painter.drawPixmap(rect, self.disabled_pixmap)
        elif self.hovered:
            painter.drawPixmap(rect, self.hover_pixmap)
        else:
            painter.drawPixmap(rect, self.normal_pixmap)
            
class AudioVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 100)
        self.bands = []
        
        self.num_leds_vertical = 8
        self.led_gap = 1.5
        
        self.color_bottom = QColor("#00ff9d")
        self.color_middle = QColor("#35ff00")
        self.color_top = QColor("#e1ff00")
        
        self.led_colors = []
        self._precompute_colors()
        # ---

    def _precompute_colors(self):
        self.led_colors = []
        for i in range(self.num_leds_vertical):
            t = i / (self.num_leds_vertical - 1)
            
            if t < 0.5:
                norm_t = t * 2
                r = self.color_bottom.red() * (1 - norm_t) + self.color_middle.red() * norm_t
                g = self.color_bottom.green() * (1 - norm_t) + self.color_middle.green() * norm_t
                b = self.color_bottom.blue() * (1 - norm_t) + self.color_middle.blue() * norm_t
            else:
                norm_t = (t - 0.5) * 2
                r = self.color_middle.red() * (1 - norm_t) + self.color_top.red() * norm_t
                g = self.color_middle.green() * (1 - norm_t) + self.color_top.green() * norm_t
                b = self.color_middle.blue() * (1 - norm_t) + self.color_top.blue() * norm_t
                
            self.led_colors.append(QColor(int(r), int(g), int(b)))

    @Slot(list)
    def update_bands(self, bands: list):
        try:
            if not isinstance(bands, (list, np.ndarray)):
                return
            new_bands = np.asarray(bands, dtype=np.float32)
            np.nan_to_num(new_bands, copy=False)
            np.clip(new_bands, 0.0, 1.0, out=new_bands)
            self.bands = new_bands
        except Exception:
            self.bands = np.array([], dtype=np.float32)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(self.rect(), QColor(25, 25, 25))
        
        num_bands = len(self.bands)
        if num_bands == 0:
            return

        led_width = self.width() / num_bands
        led_height = self.height() / self.num_leds_vertical
        
        last_leds_to_light = -1
        for i, band_value in enumerate(self.bands):
            
            leds_to_light = int(band_value * self.num_leds_vertical)
            
            x = i * led_width
            
            if leds_to_light == 0:
                leds_to_light = int(last_leds_to_light * 0.8)
            
            for j in range(leds_to_light):
                color = self.led_colors[j]
                
                y = self.height() - (j + 1) * led_height
                
                led_rect = QRectF(x + self.led_gap,
                                  y + self.led_gap,
                                  led_width - 2 * self.led_gap,
                                  led_height - 2 * self.led_gap)
                
                painter.fillRect(led_rect, color)
            last_leds_to_light = leds_to_light
        
    def paintEvent2(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            
            if self.error_message:
                painter.setPen(Qt.GlobalColor.red)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.error_message)
                return

            num_bands = len(self.bands)

            if num_bands == 0:
                return

            bar_width = self.width() / num_bands
            
            if bar_width < 1:
                return 

            gap = bar_width * 0.2
            bar_sub_width = bar_width - gap
            
            gradient = QLinearGradient(0, self.height(), 0, 0)
            gradient.setColorAt(0, QColor("green"))
            gradient.setColorAt(0.5, QColor("yellow"))
            gradient.setColorAt(1, QColor("red"))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            
            current_height = self.height()
            
            rects_to_draw = []
            for i, val in enumerate(self.bands):
                bar_height = val * current_height
                
                x = i * bar_width + (gap / 2)
                y = current_height - bar_height
                
                rects_to_draw.append(QRectF(x, y, bar_sub_width, bar_height))

            if rects_to_draw:
                painter.drawRects(rects_to_draw)

        except Exception as e:
            print(f"!!! FATAL ERROR in paintEvent: {e}")

class AudioProcessor(QObject):
    bands_ready = Signal(list)
    
    def __init__(self, num_bands=32):
        super().__init__()
        self.num_bands = num_bands
        self._audio_buffer = bytearray()

    @Slot(bytes)
    def process_data(self, audio_data: bytes):
        self._audio_buffer.extend(audio_data)
        
        chunk_size = 4096 * CHANNELS * 2
        
        while len(self._audio_buffer) >= chunk_size:
            chunk = self._audio_buffer[:chunk_size]
            del self._audio_buffer[:chunk_size]
            
            samples = np.frombuffer(chunk, dtype=np.int16)
            
            if CHANNELS == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)

            window = np.hanning(len(samples))
            samples = samples * window

            fft_result = np.fft.rfft(samples)
            fft_freq = np.fft.rfftfreq(len(samples), 1.0 / RATE)
            
            magnitude = np.abs(fft_result)

            log_magnitude = 20 * np.log10(magnitude + 1e-9)
            log_magnitude_normalized = np.clip((log_magnitude - 20) / 80, 0, 1)

            bands = self._group_into_bands(log_magnitude_normalized, fft_freq)
            
            if not np.all(np.isfinite(bands)):
                print(f"!!! Processor WARNING: Found non-finite values in bands: {bands}")
                bands = np.nan_to_num(bands).tolist()
            
            self.bands_ready.emit(bands)

    def _group_into_bands(self, data, freqs):
        bands = [0.0] * self.num_bands
        
        min_freq = 20
        max_freq = 20000

        log_bounds = np.logspace(np.log10(min_freq), np.log10(max_freq), self.num_bands + 1)
        
        band_counts = [0] * self.num_bands

        for i in range(len(freqs)):
            freq = freqs[i]
            if freq == 0: continue

            for j in range(self.num_bands):
                if log_bounds[j] <= freq < log_bounds[j+1]:
                    bands[j] = max(bands[j], data[i])
                    break
        
        return bands

# ==========================================
# 2. 自定义电台列表项组件
# ==========================================
class StationItemWidget(QWidget):
    """用于 QListWidget 的自定义行，包含图标、电台名和播放按钮"""
    def __init__(self, station_name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 左侧图标 (这里用一个简单的黑圈模拟，实际可替换为QIcon)
        self.icon_label = QLabel("🎧") 
        self.icon_label.setFont(QFont("Arial", 16))
        
        # 中间电台名称
        self.name_label = QLabel(station_name)
        self.name_label.setFont(QFont("Arial", 11, QFont.Bold))
        
        # 右侧播放按钮
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(28, 28)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border-radius: 14px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #333; }
        """)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.btn_play)

class ScrollingLabel(QWidget):
    def __init__(self, font: QFont, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.status_font = font
        
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(40)
        self.scroll_timer.timeout.connect(self._update_scroll_offset)

        self.scroll_offset = 0
        self.scrolling_text = ""
        self.scroll_loop_point = 0
        self.status_report = ""

    @Slot(str)
    def update_status_report(self, status_text: str):
        self.scroll_timer.stop()
        self.scroll_offset = 0
        self.status_report = status_text
        
        fm = QFontMetrics(self.status_font)
        text_width = fm.horizontalAdvance(self.status_report)
        
        # 如果文字宽度大于控件宽度，开启跑马灯
        if text_width > self.width() and self.width() > 0:
            gap = "    "
            self.scrolling_text = self.status_report + gap + self.status_report
            self.scroll_loop_point = fm.horizontalAdvance(self.status_report + gap)
            self.scroll_timer.start()
            
        self.update()

    @Slot()
    def _update_scroll_offset(self):
        self.scroll_offset += 1
        if self.scroll_offset >= self.scroll_loop_point:
            self.scroll_offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.status_font)
        # 这里我用了深灰色，你也可以改回你旧代码里的 Qt.GlobalColor.green
        painter.setPen(Qt.GlobalColor.black) 
        
        rect = self.rect()
        painter.setClipRect(rect)
        
        if self.scroll_timer.isActive():
            painter.drawText(rect.x() - self.scroll_offset, rect.y(),
                             self.scroll_loop_point * 2, rect.height(),
                             Qt.AlignmentFlag.AlignVCenter, self.scrolling_text)
        else:
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
                             self.status_report)

# ==========================================
# 3. 主 Gadget 界面
# ==========================================
class InternetRadioGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        
        # --- 数据与业务层初始化 ---
        self.api = RadioBrowserApi()
        self.player = RadioPlayer(parent=self)
        self.current_playing_index = 0
        self.is_playing = False
        
        # --- UI 初始化 ---
        self.setWindowTitle('iRadio')
        self.resize(320, 600)  # 调整为类似手机屏幕的垂直比例
        self.setStyleSheet("background-color: white;")
        
        self._load_assets()
        
        self.setup_ui()
        self.initization()
        
    def _load_assets(self):
        # 补全你图中的图片名称
        asset_files = [
            "button-play.png", "button-play-hover.png", "button-play-disable.png",
            "button-pause.png", "button-pause-hover.png", "button-pause-disable.png",
            "button-next.png", "button-next-hover.png", "button-next-disable.png", # 假设你有disable，没有就用普通图代替
            "button-prev.png", "button-prev-hover.png", "button-prev-disable.png",
        ]
        self.assets = {}
        for filename in asset_files:
            key = filename.split('.')[0]
            path = os.path.join(self.gadget_assets_path, filename)
            self.assets[key] = QPixmap(path)

    def setup_ui(self):
        self.setFixedWidth(320)
        
        """构建现代化的垂直布局"""
        top_layout = QVBoxLayout(self)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # 2. 创建一个主容器
        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet("""
            QWidget#MainContainer {
                background-color: white;
                border: 2px solid black;
                border-radius: 20px;
            }
        """)
        
        top_layout.addWidget(self.main_container)

        # 3. 将原本的 main_layout 挂载到主容器上，而不是 self 上
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 4. 构建黑色标题栏
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)
        # 标题栏需要上方的圆角适配外框，下方直角
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: black;
                border-top-left-radius: 17px;  /* 比外框小一点，防止溢出 */
                border-top-right-radius: 17px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        lbl_titlebar = QLabel("iRadio - Internet Radio based on GSF")
        lbl_titlebar.setFont(QFont("Arial", 9, QFont.Bold))
        lbl_titlebar.setStyleSheet("color: white; background-color: transparent;")
        title_layout.addWidget(lbl_titlebar, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.title_bar)
        
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        main_layout.addLayout(content_layout)

        # 1. 顶部封面
        self.favicon = CircularFavicon(size=140, parent=self)
        fav_layout = QHBoxLayout()
        fav_layout.addWidget(self.favicon, alignment=Qt.AlignCenter)
        content_layout.addLayout(fav_layout)

        # 2. 标题和副标题
        #self.lbl_title = QLabel("INTERNET RADIO")
        #self.lbl_title.setFont(QFont("Arial", 14, QFont.Bold))
        #self.lbl_title.setAlignment(Qt.AlignCenter)
        
        self.lbl_title = ScrollingLabel(QFont("Arial", 14, QFont.Bold))
        self.lbl_subtitle = QLabel("Loading stations...")
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        
        self.lbl_subtitle = QLabel("Loading stations...")
        self.lbl_subtitle.setFont(QFont("Arial", 10))
        self.lbl_subtitle.setStyleSheet("color: #666;")
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        
        content_layout.addWidget(self.lbl_title)
        content_layout.addWidget(self.lbl_subtitle)

        # 3. 播放控制栏 (上一首, 播放/暂停, 下一首)
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignCenter)
        control_layout.setSpacing(20)
        self.btn_prev =None
        self.btn_play =None
        self.btn_pause =None
        self.btn_next =None
        
        self.btn_prev = QImageButton((48, 48), 
            self.assets["button-prev"], 
            self.assets["button-prev-hover"], 
            self.assets["button-prev"],
            callback=self.play_prev)
            
        self.btn_play = QImageButton((64, 64), 
            self.assets["button-play"], 
            self.assets["button-play-hover"], 
            self.assets["button-play-disable"],
            callback=self.playFM)
            
        self.btn_pause = QImageButton((64, 64), 
            self.assets["button-pause"],
            self.assets["button-pause-hover"], 
            self.assets["button-pause-disable"],
            callback=self.pauseFM)
        
        self.btn_next = QImageButton((48, 48), 
            self.assets["button-next"], 
            self.assets["button-next-hover"], 
            self.assets["button-next"],
            callback=self.play_next)

        # 初始化时隐藏暂停按钮
        self.btn_pause.hide()

        self.btn_prev.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_next.setEnabled(False)

        control_layout.addWidget(self.btn_prev)
        control_layout.addWidget(self.btn_play)
        control_layout.addWidget(self.btn_pause) # Play 和 Pause 占同一个坑位
        control_layout.addWidget(self.btn_next)
        content_layout.addLayout(control_layout)

        # 4. 音量控制
        vol_layout = QHBoxLayout()
        lbl_vol = QLabel("Volume")
        lbl_vol.setFont(QFont("Arial", 10))
        
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(80)
        # 现代化的纤细滑动条样式
        self.slider_vol.setStyleSheet("""
            QSlider::groove:horizontal {
                border-radius: 2px;
                height: 4px;
                background: #E0E0E0;
            }
            QSlider::handle:horizontal {
                background: black;
                width: 14px;
                height: 14px;
                margin: -5px 0; 
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: black;
                border-radius: 2px;
            }
        """)
        
        vol_layout.addWidget(lbl_vol)
        vol_layout.addWidget(self.slider_vol)
        content_layout.addLayout(vol_layout)

        # 5. 搜索框
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CCC;
                border-radius: 10%;
                padding: 8px 15px;
                font-size: 12px;
                background-color: #F9F9F9;
            }
        """)
        content_layout.addWidget(self.search_bar)

        # 6. 电台列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border-bottom: 1px solid #F0F0F0;
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: #F5F5F5;
                color: black;
            }
        """)
        
        self.list_widget.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.loaded_station_count = 0  # 记录当前已经加载了多少个电台
        self.BATCH_SIZE = 40           # 每次只加载 40 个，保证瞬间完成不卡顿
        
        content_layout.addWidget(self.list_widget)

    def create_round_button(self, text, size):
        """辅助方法：创建黑色圆形控制按钮"""
        btn = QPushButton(text)
        btn.setFixedSize(size, size)
        radius = size // 2
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: black;
                color: white;
                border-radius: {radius}px;
                font-size: {int(size*0.4)}px;
            }}
            QPushButton:hover {{
                background-color: #333333;
            }}
            QPushButton:disabled {{
                background-color: #CCCCCC;
            }}
        """)
        btn.setEnabled(False) # 初始化时禁用，直到 API 加载完成
        return btn

    # --- 后台逻辑维持原样，调整了 UI 更新的方式 ---
    def initization(self):
        self.init_thread = QThread(parent=self)
        self.init_worker = InitializationWorker(self.api)
        self.init_worker.moveToThread(self.init_thread)

        self.init_worker.status_updated.connect(self.update_status_report)
        self.init_worker.initialization_finished.connect(self.on_initialization_finished)
        
        self.init_thread.started.connect(self.init_worker.run)
        self.init_thread.finished.connect(self.init_thread.deleteLater)
        self.init_thread.start()

    @Slot(str)
    def update_status_report(self, status_text: str):
        # 原来复杂的滚动文本逻辑，现在直接更新副标题即可
        self.lbl_subtitle.setText(status_text)

    @Slot()
    def on_initialization_finished(self):
        self.update_status_report("Ready")
        
        self.btn_prev.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.btn_next.setEnabled(True)
        
        self.populate_radio_list()
        self.init_thread.quit()

    def populate_radio_list(self):
        """初始化列表，重置计数器并加载第一批"""
        self.list_widget.clear()
        self.loaded_station_count = 0
        self._load_more_stations()

    def _load_more_stations(self):
        """核心逻辑：分批生成带 Widget 的列表项"""
        if not self.api.radio_data:
            return

        total_stations = len(self.api.radio_data)
        
        # 如果已经全部加载完毕，就不用再处理了
        if self.loaded_station_count >= total_stations:
            return 

        # 计算这一批应该加载到哪个索引
        end_index = min(self.loaded_station_count + self.BATCH_SIZE, total_stations)

        # 只循环生成这一批次 (比如 40 个)，速度极快，不会卡死主线程
        for i in range(self.loaded_station_count, end_index):
            radio = self.api.radio_data[i]
            
            # 防止名字太长
            name = radio.get('name', 'Unknown Station')
            if len(name) > 25: 
                name = name[:22] + "..."
                
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 50)) # 设置行高
            
            custom_widget = StationItemWidget(name)
            
            # 【注意这里的 lambda 写法】：必须把 i 绑定到默认参数 idx 上，否则所有的按钮都会播放最后一首！
            custom_widget.btn_play.clicked.connect(
                lambda checked=False, idx=i: self.play_station_by_index(idx)
            )
            
            self.list_widget.setItemWidget(item, custom_widget)

        # 更新已加载的数量
        self.loaded_station_count = end_index

    @Slot(int)
    def _on_scroll(self, value):
        """当滚动条发生变化时触发"""
        scrollbar = self.list_widget.verticalScrollBar()
        # 如果滚动条滑到了最底部（或者距离底部还有一点距离），就加载下一批
        if value >= scrollbar.maximum() - 2:
            self._load_more_stations()

    def play_station_by_index(self, index):
        self.current_playing_index = index
        self.playFM()

    def playFM(self):
        if not self.api.radio_data:
            return
            
        radio = self.api.radio_data[self.current_playing_index]
        
        self.favicon.load_from_url(radio.get('favicon', ''))
        
        # 触发跑马灯！
        title = radio.get('name', 'Unknown Station').upper()
        self.lbl_title.update_status_report(title)
        
        # 动态隐藏 Play，显示 Pause
        self.btn_play.hide()
        self.btn_pause.show()
        
        self.player.playFM(radio)

    def pauseFM(self):
        self.lbl_title.update_status_report("PAUSED")
        
        # 动态隐藏 Pause，显示 Play
        self.btn_pause.hide()
        self.btn_play.show()
        
        self.player.pauseFM()
    def toggle_play_pause(self):
        if self.is_playing:
            self.pauseFM()
        else:
            self.playFM()

    def play_next(self):
        if not self.api.radio_data: return
        self.current_playing_index = (self.current_playing_index + 1) % len(self.api.radio_data)
        self.playFM()

    def play_prev(self):
        if not self.api.radio_data: return
        self.current_playing_index = (self.current_playing_index - 1) % len(self.api.radio_data)
        self.playFM()
        
if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print("Error: need to provide the gadget_path as argument")
            sys.exit(1)
        
        gadget_path_arg = sys.argv[1]
    
        app = QApplication(sys.argv)
        
        gadget = InternetRadioGadget(gadget_path=gadget_path_arg)
        gadget.show()
        sys.exit(app.exec())
    except Exception as e:
        print(e)