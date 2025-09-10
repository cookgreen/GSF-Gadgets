import sys
import os
import random
import numpy as np
from typing import Optional, Callable, Tuple, Any
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from gsf.gadget_base import BaseGadget

from radio_browser_api import *
from radio_player import *

AUDIO_FORMAT = "S16N"
CHANNELS = 2
RATE = 44100

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

class QImageButton:
    def __init__(self,
                 pos: tuple[int, int],
                 size: tuple[int, int],
                 normal_pixmap: QPixmap,
                 hover_pixmap: QPixmap,
                 disabled_pixmap: QPixmap,
                 callback: Optional[Callable[..., None]] = None):
        self.rect = QRect(pos[0], pos[1], size[0], size[1])
        
        self.normal_pixmap = normal_pixmap
        self.hover_pixmap = hover_pixmap
        self.disabled_pixmap = disabled_pixmap
        
        self.callback = callback
        
        self.hovered = False
        self.isEnabled = True
        self.isVisible = True 

    def checkIsEnter(self, point: QPoint):
        return self.rect.contains(point)

    def mouseMove(self, point: QPoint) -> bool:
        if not self.isEnabled:
            return False
        
        is_over = self.checkIsEnter(point)
        if is_over != self.hovered:
            self.hovered = is_over
            return True 
        return False

    def mousePress(self):
        if self.isEnabled and self.callback:
            self.callback()
            
    def paint(self, painter: QPainter):
        if not self.isVisible:
            return

        if not self.isEnabled:
            painter.drawPixmap(self.rect, self.disabled_pixmap)
        elif self.hovered:
            painter.drawPixmap(self.rect, self.hover_pixmap)
        else:
            painter.drawPixmap(self.rect, self.normal_pixmap)
            
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
        """在初始化时计算并缓存每一行LED的颜色，避免在paintEvent中重复计算。"""
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

        for i, band_value in enumerate(self.bands):
            
            leds_to_light = int(band_value * self.num_leds_vertical)
            
            for j in range(leds_to_light):
                color = self.led_colors[j]
                
                x = i * led_width
                y = self.height() - (j + 1) * led_height
                
                led_rect = QRectF(x + self.led_gap,
                                  y + self.led_gap,
                                  led_width - 2 * self.led_gap,
                                  led_height - 2 * self.led_gap)
                
                painter.fillRect(led_rect, color)
        
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

class InternetRadioGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        
        self.setMouseTracking(True)
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        self.assets: Dict[str, QPixmap] = {}
        
        self._load_assets()
        
        self.api = RadioBrowserApi()
        
        self.status_font = QFont("Arial", 15)
        self.status_rect = QRect(21, 15, 144, 37)

        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(40)
        self.scroll_timer.timeout.connect(self._update_scroll_offset)

        self.scroll_offset = 0
        self.scrolling_text = ""
        self.scroll_loop_point = 0
        
        self.status_report = ""
        self.current_playing_index = 0
        
        self.initization()
        
        # --- specific logic ---
        self.setWindowTitle('Internet Radio')
        self.resize(384, 174)
        
        self.hasReseted = True
        
        # --- Audio Visualizer ---
        self.player = RadioPlayer(parent=self)
        
        self.visualizer = AudioVisualizer(self)
        self.visualizer.setGeometry(21, 60, 340, 15)
        self.visualizer.setFixedHeight(65)
        self.visualizer.show()
        
        self.processor = AudioProcessor(num_bands=32)
        
        self.processing_thread = QThread(parent=self)
        self.processor.moveToThread(self.processing_thread)
        
        self.player.audio_data_ready.connect(self.processor.process_data)
        self.processor.bands_ready.connect(self.visualizer.update_bands)
        
        self.processing_thread.start()
        
        # --- Timer ---
        timer = QTimer(self)
        timer.timeout.connect(self.update) # update() will trigger paintEvent
        timer.start(1000)

        self.hovered_button: Optional[QImageButton] = None
        self.all_buttons: List[QImageButton] = []
        
        # --- load images ---
        self.main_panel = QImage(os.path.join(self.gadget_assets_path, "main_panel.png"))
        
        self._create_buttons()
        
    def _load_assets(self):
        asset_files = [
            "button-play.png",
            "button-play-hover.png",
            "button-play-disable.png",
            "button-pause.png",
            "button-pause-hover.png",
            "button-pause-disable.png",
            "button-random.png",
            "button-random-hover.png",
            "button-random-disable.png",
            "button-stop.png",
            "button-stop-hover.png",
            "button-stop-disable.png",
        ]

        for filename in asset_files:
            key = filename.split('.')[0]
            path = os.path.join(self.gadget_assets_path, filename)
            self.assets[key] = QPixmap(path)
    
    def _create_buttons(self):
        self.btnPlay = QImageButton((168, 124), (48, 48), 
            self.assets["button-play"],
            self.assets["button-play-hover"],
            self.assets["button-play-disable"],
            callback=self.playFM)
        self.btnPlay.isEnabled = False
        
        self.btnPause = QImageButton((168, 124), (48, 48), 
            self.assets["button-pause"],
            self.assets["button-pause-hover"],
            self.assets["button-pause-disable"],
            callback=self.pauseFM)
        self.btnPause.isEnabled = False
        
        self.btnRandom = QImageButton((76, 131), (34, 34), 
            self.assets["button-random"],
            self.assets["button-random-hover"],
            self.assets["button-random-disable"],
            callback=self.randomPlayFM)
        self.btnRandom.isEnabled = False
        
        self.btnStop = QImageButton((275, 131), (34, 34), 
            self.assets["button-stop"],
            self.assets["button-stop-hover"],
            self.assets["button-stop-disable"],
            callback=self.stopFM)
        self.btnStop.isEnabled = False
            
        self.all_buttons.append(self.btnRandom)
        self.all_buttons.append(self.btnStop)
        self.all_buttons.append(self.btnPlay)
    
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
        self.scroll_timer.stop()
        self.scroll_offset = 0
        
        self.status_report = status_text
        
        fm = QFontMetrics(self.status_font)
        text_width = fm.horizontalAdvance(self.status_report)
        
        if text_width > self.status_rect.width():
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

    @Slot()
    def on_initialization_finished(self):
        self.update_status_report("Ready")
        
        self.btnPlay.isEnabled = True
        self.btnPause.isEnabled = True
        self.btnRandom.isEnabled = True
        self.btnStop.isEnabled = True
        
        self.init_thread.quit()
    
    def playFM(self):
        radio = self.api.radio_data[self.current_playing_index]
        
        self.update_status_report(f"Playing {radio['name']}")
        self.player.playFM(radio)
    
    def pauseFM(self):
        self.update_status_report("Paused")
        self.player.pauseFM()
        
    def randomPlayFM(self):
        self.current_playing_index = random.randint(0, len(self.api.radio_data) - 1)
        radio = self.api.radio_data[self.current_playing_index]
        
        self.update_status_report(f"Playing {radio['name']}")
        
        self.player.playFM(radio)
    
    def stopFM(self):
        self.update_status_report("Ready")
        self.player.stopFM()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        current_hover = None
        for btn in self.all_buttons:
            if btn.isVisible and btn.checkIsEnter(event.pos()):
                current_hover = btn
                break
        
        if self.hovered_button is not current_hover:
            if self.hovered_button:
                self.hovered_button.hovered = False
            if current_hover:
                current_hover.hovered = True
            
            self.hovered_button = current_hover
            self.update()

        super().mouseMoveEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            for btn in self.all_buttons:
                if btn.isVisible and btn.isEnabled and btn.checkIsEnter(event.pos()):
                    btn.mousePress()
                    return
        super().mousePressEvent(event)
        
    def paintEvent(self, event):
        """only care about how to paint，other are handled by base-class"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        target_rect = QRect(0, 0, 384, 178)
        painter.drawImage(target_rect, self.main_panel)
        
        painter.fillRect(self.status_rect, Qt.GlobalColor.black)

        painter.setClipRect(self.status_rect)
        
        painter.setFont(self.status_font)
        painter.setPen(Qt.GlobalColor.green)
        
        if self.scroll_timer.isActive():
            painter.drawText(self.status_rect.x() - self.scroll_offset, self.status_rect.y(),
                             self.scroll_loop_point * 2, self.status_rect.height(), # 提供足够宽的绘制区域
                             Qt.AlignmentFlag.AlignVCenter, self.scrolling_text)
        else:
            painter.drawText(self.status_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             self.status_report)
        
        painter.setClipping(False)
        
        self.btnRandom.paint(painter)
        self.btnStop.paint(painter)
        
        if self.player.vlc_player.is_playing():
            self.btnPause.paint(painter)
            
            if self.btnPause not in self.all_buttons:
                self.all_buttons.append(self.btnPause)
            if self.btnPlay in self.all_buttons:
                self.all_buttons.remove(self.btnPlay)
        else:
            self.btnPlay.paint(painter)
            
            if self.btnPlay not in self.all_buttons:
                self.all_buttons.append(self.btnPlay)
            if self.btnPause in self.all_buttons:
                self.all_buttons.remove(self.btnPause)
        
        painter.setFont(QFont("Arial", 15))
        painter.setPen(Qt.GlobalColor.green)
        
        painter.end()

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