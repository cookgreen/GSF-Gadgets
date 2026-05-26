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

class CircularImageLayer(QWidget):
    """纯粹的绘图层：强制物理裁切图片为圆形"""
    def __init__(self, size, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.pixmap = None

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update() # 触发重绘

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 1. 核心：建立圆形物理裁切路径
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        painter.setClipPath(path)
        
        # 2. 画图
        if self.pixmap and not self.pixmap.isNull():
            # 缩放并居中对齐
            scaled = self.pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # 如果没有图，画一个深色底
            painter.fillRect(self.rect(), QColor("#1A1A1A"))

class CircularFavicon(QWidget):
    """封装层：整合黑色外阴影与白色内光晕"""
    def __init__(self, size=140, default_img_path="", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        
        # ==================================
        # 底层：负责黑色凸起阴影
        # ==================================
        self.shadow_layer = QWidget(self)
        self.shadow_layer.setFixedSize(size, size)
        # 用 QSS 画一个纯黑的圆作为阴影的发光体
        self.shadow_layer.setStyleSheet(f"background-color: black; border-radius: {size//2}px;")
        
        outer_shadow = QGraphicsDropShadowEffect(self)
        outer_shadow.setBlurRadius(40)
        outer_shadow.setColor(QColor(0, 0, 0, 180)) # 深色阴影
        outer_shadow.setOffset(0, 8)
        self.shadow_layer.setGraphicsEffect(outer_shadow)

        # ==================================
        # 顶层：负责画图 + 白色高级光晕
        # ==================================
        # 这一层叠在 shadow_layer 正上方
        self.glow_layer = CircularImageLayer(size, parent=self)
        
        inner_glow = QGraphicsDropShadowEffect(self)
        inner_glow.setBlurRadius(30)
        inner_glow.setColor(QColor(255, 255, 255, 120)) # 半透明白色光晕
        inner_glow.setOffset(0, 0)
        self.glow_layer.setGraphicsEffect(inner_glow)

        # ==================================
        # 数据加载逻辑
        # ==================================
        self.default_pixmap = QPixmap()
        if default_img_path and os.path.exists(default_img_path):
            self.default_pixmap = QPixmap(default_img_path)
            self.glow_layer.set_pixmap(self.default_pixmap)

        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._on_image_downloaded)

    def load_from_url(self, url_str: str):
        # 切换电台时，瞬间切回默认图
        self.glow_layer.set_pixmap(self.default_pixmap)
        
        if not url_str: return
        request = QNetworkRequest(QUrl(url_str))
        self.network_manager.get(request)

    def _on_image_downloaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            img_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(img_data) and not pixmap.isNull():
                self.glow_layer.set_pixmap(pixmap)
        reply.deleteLater()
        
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
    clicked = Signal()

    def __init__(self, size: tuple[int, int],
                 normal_pixmap: QPixmap,
                 hover_pixmap: QPixmap,
                 disabled_pixmap: QPixmap,
                 callback=None, parent=None):
        super().__init__(parent)
        
        self.setFixedSize(size[0], size[1])
        
        self.normal_pixmap = normal_pixmap
        self.hover_pixmap = hover_pixmap
        self.disabled_pixmap = disabled_pixmap
        self.callback = callback
        
        self.hovered = False
        self._is_enabled = True 
        self.setMouseTracking(True) 

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

class StationItemWidget(QWidget):
    def __init__(self, station_name, assets, assets_path, parent=None):
        super().__init__(parent)
        self.assets = assets 
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.icon_label = QLabel("🎧") 
        self.icon_label.setFont(QFont("Arial", 14))
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        self.wave_movie = QMovie(os.path.join(assets_path, "wave.gif"))
        self.wave_movie.setScaledSize(QSize(20, 20)) 
        
        self.name_label = QLabel(station_name)
        self.name_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.name_label.setStyleSheet("color: #DDDDDD; background-color: transparent;")
        
        self.btn_play = QImageButton((28, 28), 
            self.assets["button-play"], 
            self.assets.get("button-play-hover", self.assets["button-play"]), 
            self.assets.get("button-play-disable", self.assets["button-play"]))
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.btn_play)

    def set_active_state(self, is_current: bool, is_playing: bool):
        """由主界面调用，动态切换图片和动图状态"""
        if is_current:
            self.setStyleSheet("StationItemWidget { background-color: #000000; border-radius: 8px; }")
            
            if is_playing:
                self.btn_play.normal_pixmap = self.assets["button-pause"]
                self.btn_play.hover_pixmap = self.assets.get("button-pause-hover", self.assets["button-pause"])
                
                self.icon_label.setMovie(self.wave_movie)
                self.wave_movie.start()
            else:
                self.btn_play.normal_pixmap = self.assets["button-play"]
                self.btn_play.hover_pixmap = self.assets.get("button-play-hover", self.assets["button-play"])
                
                self.wave_movie.stop()
                self.icon_label.clear()
                self.icon_label.setText("🎧")
        else:
            self.setStyleSheet("StationItemWidget { background-color: transparent; }")
            
            self.btn_play.normal_pixmap = self.assets["button-play"]
            self.btn_play.hover_pixmap = self.assets.get("button-play-hover", self.assets["button-play"])
            
            self.wave_movie.stop()
            self.icon_label.clear()
            self.icon_label.setText("🎧")
            
        self.btn_play.update()

class ScrollingLabel(QWidget):
    def __init__(self, text, font: QFont, color: QColor = Qt.GlobalColor.black, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.status_font = font
        self.text_color = color
        
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(40)
        self.scroll_timer.timeout.connect(self._update_scroll_offset)

        self.scroll_offset = 0
        self.scrolling_text = ""
        self.scroll_loop_point = 0
        self.text = text

    @Slot(str)
    def update_status_report(self, status_text: str):
        self.scroll_timer.stop()
        self.scroll_offset = 0
        self.text = status_text
        
        fm = QFontMetrics(self.status_font)
        text_width = fm.horizontalAdvance(self.text)
        
        if text_width > self.width() and self.width() > 0:
            gap = "    "
            self.scrolling_text = self.text + gap + self.text
            self.scroll_loop_point = fm.horizontalAdvance(self.text + gap)
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
        painter.setPen(self.text_color)
        
        rect = self.rect()
        painter.setClipRect(rect)
        
        if self.scroll_timer.isActive():
            painter.drawText(rect.x() - self.scroll_offset, rect.y(),
                             self.scroll_loop_point * 2, rect.height(),
                             Qt.AlignmentFlag.AlignVCenter, self.scrolling_text)
        else:
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
                             self.text)

class InternetRadioGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        
        self.api = RadioBrowserApi()
        self.player = RadioPlayer(parent=self)
        self.current_playing_index = 0
        self.is_playing = False
        
        self.is_landscape = True # 默认是宽屏桌面模式
        
        self.setWindowTitle('iRadio')
        self.resize(320, 600) 
        #self.setStyleSheet("background-color: white;")
        
        self._load_assets()
        
        self.setup_ui()
        self.initization()
        
    def _load_assets(self):
        asset_files = [
            "iRadio-default.png",
            "button-play.png", "button-play-hover.png",
            "button-pause.png", "button-pause-hover.png",
            "button-next.png", "button-next-hover.png",
            "button-prev.png", "button-prev-hover.png",
            "button-volume.png", "button-volume-hover.png",
            "button-expand.png", "button-less.png",
            "button-volume-none.png", "button-volume-none-hover.png",
        ]
        self.assets = {}
        for filename in asset_files:
            key = filename.split('.')[0]
            path = os.path.join(self.gadget_assets_path, filename)
            self.assets[key] = QPixmap(path)

    def setup_ui(self):
        self.setFixedWidth(320)
        
        top_layout = QVBoxLayout(self)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet("""
            QWidget#MainContainer {
                background-color: transparent; /* 【关键】背景透明 */
                border: 1px solid rgba(255, 255, 255, 0.15); /* 边框改成半透明的白边，更有玻璃质感 */
                border-radius: 20px;
            }
        """)
        
        top_layout.addWidget(self.main_container)
        
        self.bg_label = QLabel(self.main_container)
        self.bg_label.setScaledContents(True)
        # 添加模糊滤镜
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(50) # 半径越大越模糊
        self.bg_label.setGraphicsEffect(blur_effect)

        # 层级 2：暗色半透明遮罩 (盖在背景图上)
        self.dark_overlay = QWidget(self.main_container)
        self.dark_overlay.setStyleSheet("""
            background-color: rgba(18, 22, 28, 0.75); /* 深灰偏蓝的半透明遮罩 */
            border-radius: 20px;
        """)

        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                                  stop:0 #3e454d, stop:1 #12171b);
                border-top-left-radius: 17px;
                border-top-right-radius: 17px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        self.btn_toggle_view = QImageButton((20, 20), 
            self.assets["button-expand"], 
            self.assets["button-expand"], 
            self.assets["button-expand"], 
            callback=self.toggle_view_mode)
        title_layout.addWidget(self.btn_toggle_view)
        
        lbl_titlebar = QLabel("iRadio - Internet Radio based on GSF")
        lbl_titlebar.setFont(QFont("Arial", 9, QFont.Bold))
        lbl_titlebar.setStyleSheet("color: #b9c0c8; background-color: transparent;")
        title_layout.addWidget(lbl_titlebar, alignment=Qt.AlignCenter)
        title_layout.addStretch() 
        
        self.main_layout.addWidget(self.title_bar)
        
        self.content_area = QWidget()
        self.content_layout = None
        self.main_layout.addWidget(self.content_area)
        
        

        self.sidebar_widget = QWidget()
        sidebar_vbox = QVBoxLayout(self.sidebar_widget)
        sidebar_vbox.setContentsMargins(15, 15, 15, 15)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 15px;
                padding: 5px 15px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
        """)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none; /* 去掉点击时的虚线框 */
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.05); /* 极弱的分割线 */
                color: #d3d7da; /* 文字浅灰 */
            }
            QListWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.1); /* 选中时微微发亮 */
                border-radius: 8px;
            }
            
            /* --- 现代胶囊悬浮滚动条 --- */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px; 
                margin: 0px; 
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2); 
                min-height: 30px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.4); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        self.list_widget.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        sidebar_vbox.addWidget(self.search_bar)
        sidebar_vbox.addWidget(self.list_widget)
        
        self.player_widget = QWidget()
        player_vbox = QVBoxLayout(self.player_widget)
        player_vbox.setContentsMargins(15, 15, 15, 15)
        player_vbox.setSpacing(10)

        default_logo_path = os.path.join(self.gadget_assets_path, "iRadio-default.png")
        self.favicon = CircularFavicon(size=140, default_img_path=default_logo_path, parent=self.main_container)
        player_vbox.addWidget(self.favicon, alignment=Qt.AlignCenter)

        #self.lbl_title = QLabel("INTERNET RADIO")
        #self.lbl_title.setFont(QFont("Arial", 14, QFont.Bold))
        #self.lbl_title.setAlignment(Qt.AlignCenter)
        
        self.lbl_title = ScrollingLabel("INTERNET RADIO", QFont("Arial", 14, QFont.Bold), QColor("#FFFFFF"))
        
        self.lbl_subtitle = ScrollingLabel("Loading...", QFont("Arial", 10), QColor(255, 255, 255, 150))
        self.lbl_subtitle.setFont(QFont("Arial", 10))
        self.lbl_subtitle.setStyleSheet("color: #666;")
        
        player_vbox.addWidget(self.lbl_title)
        player_vbox.addWidget(self.lbl_subtitle)

        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignCenter)
        control_layout.setSpacing(20)
        
        self.btn_prev = QImageButton((48, 48), 
            self.assets["button-prev"], 
            self.assets["button-prev-hover"], 
            self.assets["button-prev"],
            callback=self.play_prev)
            
        self.btn_play = QImageButton((64, 64), 
            self.assets["button-play"], 
            self.assets["button-play-hover"], 
            self.assets["button-play"],
            callback=self.playFM)
            
        self.btn_pause = QImageButton((64, 64), 
            self.assets["button-pause"],
            self.assets["button-pause-hover"], 
            self.assets["button-pause"],
            callback=self.pauseFM)
        
        self.btn_next = QImageButton((48, 48), 
            self.assets["button-next"], 
            self.assets["button-next-hover"], 
            self.assets["button-next"],
            callback=self.play_next)

        self.btn_pause.hide()

        self.btn_prev.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_next.setEnabled(False)

        control_layout.addWidget(self.btn_prev)
        control_layout.addWidget(self.btn_play)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_next)
        player_vbox.addLayout(control_layout)

        vol_layout = QHBoxLayout()
        vol_layout.setAlignment(Qt.AlignVCenter)
        
        self.btn_volume = QImageButton((24, 24), 
            self.assets["button-volume"], 
            self.assets.get("button-volume-hover", self.assets["button-volume"]), 
            self.assets.get("button-volume-disable", self.assets["button-volume"]),
            callback=self.toggle_mute)
        
        self.last_volume = 80
        
        handle_img = os.path.join(self.gadget_assets_path, "slider-handle.png").replace('\\', '/')
        handle_hover_img = os.path.join(self.gadget_assets_path, "slider-handle-hover.png").replace('\\', '/')
        
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(self.last_volume)
        self.slider_vol.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border-radius: 2px;
                height: 4px;
                background: #E0E0E0; /* 保持纤细滑槽 */
            }}
            QSlider::sub-page:horizontal {{
                background: black; /* 保持已划过区域为黑色 */
                border-radius: 2px;
            }}
            
            /* --- 【核心修改】：使用 PNG 图片替换默认 Handle --- */
            QSlider::handle:horizontal {{
                background-image: url({handle_img}); /* 指向你的图片 */
                width: 14px;  /* 必须设置，并且和图片尺寸一致 */
                height: 14px;
                margin: -5px 0; /* 用于让 14px 的 handle 在 4px 的 groove 中居中 */
                border-radius: 7px; /* 确保 QSS 将其处理为圆形裁剪 */
            }}
            QSlider::handle:horizontal:hover {{
                background-image: url({handle_hover_img}); /* 悬停图片 */
            }}
            QSlider::handle:horizontal:disabled {{
                background-image: url({handle_hover_img}); /* 禁用图片 */
            }}
        """)
        
        self.slider_vol.valueChanged.connect(self.change_volume)
        self.is_muted = False
        
        vol_layout.addWidget(self.btn_volume)
        vol_layout.addWidget(self.slider_vol)
        player_vbox.addLayout(vol_layout)
        
        
        self.loaded_station_count = 0 
        self.BATCH_SIZE = 40 
        
        self.apply_view_layout()
        
    def resizeEvent(self, event):
        """确保背景图和遮罩始终铺满整个主容器"""
        super().resizeEvent(event)
        if hasattr(self, 'main_container') and hasattr(self, 'bg_label'):
            self.bg_label.resize(self.main_container.size())
            self.dark_overlay.resize(self.main_container.size())
        
    def apply_view_layout(self):
        """根据 is_landscape 状态重新排布界面"""
        
        old_layout = self.content_area.layout()
        if old_layout:
            # 1. 先把我们辛辛苦苦写的控件从旧布局里摘出来（防止被一起销毁）
            old_layout.removeWidget(self.sidebar_widget)
            old_layout.removeWidget(self.player_widget)
            
            QWidget().setLayout(old_layout)

        if self.is_landscape:
            new_layout = QHBoxLayout(self.content_area)
            new_layout.addWidget(self.sidebar_widget, 1)
            new_layout.addWidget(self.player_widget, 1)
            self.setFixedWidth(600)
            self.resize(600, 300) 
        else:
            new_layout = QVBoxLayout(self.content_area)
            new_layout.addWidget(self.player_widget)
            new_layout.addWidget(self.sidebar_widget)
            self.setFixedWidth(320)
            self.resize(320, 600)

        self.content_area.setLayout(new_layout)

    def toggle_view_mode(self):
        """切换模式按钮的逻辑"""
        self.is_landscape = not self.is_landscape
        if self.is_landscape:
            self.btn_toggle_view.normal_pixmap = self.assets["button-expand"]
            self.btn_toggle_view.hover_pixmap = self.assets.get("button-expand-hover", self.assets["button-expand"])
        else:
            self.btn_toggle_view.normal_pixmap = self.assets["button-less"]
            self.btn_toggle_view.hover_pixmap = self.assets.get("button-less-hover", self.assets["button-less"])
        self.apply_view_layout()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.last_volume = self.slider_vol.value()
            self.slider_vol.setValue(0)
            self.btn_volume.normal_pixmap = self.assets["button-volume-none"]
            self.btn_volume.hover_pixmap = self.assets.get("button-volume-none-hover", self.assets["button-volume-none"])
        else:
            self.slider_vol.setValue(self.last_volume if self.last_volume > 0 else 50)
            self.btn_volume.normal_pixmap = self.assets["button-volume"]
            self.btn_volume.hover_pixmap = self.assets.get("button-volume-hover", self.assets["button-volume"])
            
        self.btn_volume.update() # 触发按钮重绘

    def change_volume(self, value):
        if hasattr(self.player, 'vlc_player'):
            self.player.vlc_player.audio_set_volume(value)
            
        if value > 0 and self.is_muted:
            self.toggle_mute()
    
    def create_round_button(self, text, size):
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
        btn.setEnabled(False)
        return btn
        
    def refresh_list_ui(self):
        """遍历当前加载的列表项，更新它们的高亮和播放状态"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                is_current = (i == self.current_playing_index)
                widget.set_active_state(is_current, self.is_playing)

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
        self.lbl_subtitle.update_status_report(status_text)

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
        
        if self.loaded_station_count >= total_stations:
            return 

        end_index = min(self.loaded_station_count + self.BATCH_SIZE, total_stations)

        for i in range(self.loaded_station_count, end_index):
            radio = self.api.radio_data[i]
            
            name = radio.get('name', 'Unknown Station')
            if len(name) > 25: 
                name = name[:22] + "..."
                
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 50))
            
            custom_widget = StationItemWidget(name, self.assets, self.gadget_assets_path)
            
            custom_widget.btn_play.clicked.connect(
                lambda checked=False, idx=i: self.play_station_by_index(idx)
            )
            
            self.list_widget.setItemWidget(item, custom_widget)

        self.loaded_station_count = end_index

    @Slot(int)
    def _on_scroll(self, value):
        """当滚动条发生变化时触发"""
        scrollbar = self.list_widget.verticalScrollBar()
        
        if value >= scrollbar.maximum() - 2:
            self._load_more_stations()

    def play_station_by_index(self, index):
        self.current_playing_index = index
        self.playFM()

    def playFM(self):
        if not self.api.radio_data:
            return
            
        radio = self.api.radio_data[self.current_playing_index]
        
        favicon_url = radio.get('favicon', '')
        self.favicon.load_from_url(favicon_url)
        
        title = radio.get('name', 'Unknown Station').upper()
        self.lbl_title.update_status_report(title)
        
        subtitle_text = radio.get('tags', '').replace(',', ' • ').upper() or radio.get('country', 'UNKNOWN')
        self.lbl_subtitle.update_status_report(subtitle_text)
        
        self.btn_play.hide()
        self.btn_pause.show()
        
        self.player.playFM(radio)
        
        self.is_playing = True
        self.refresh_list_ui()

    def pauseFM(self):
        self.lbl_title.update_status_report("PAUSED")
        
        self.btn_pause.hide()
        self.btn_play.show()
        
        self.player.pauseFM()
        
        self.is_playing = False
        self.refresh_list_ui()
        
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