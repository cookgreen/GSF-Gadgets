import sys
import os
from typing import Optional, Callable, Dict, List
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from enum import Enum, auto

from gsf.gadget_base import BaseGadget

from vlc_player import *

class TimerStatus(Enum):
    RESET = auto()
    RUNNING = auto()
    PAUSE = auto()

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

class TimerGadget(BaseGadget):
    def __init__(self, gadget_path):
        super().__init__(gadget_path)
        
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        self.gadget_sounds_path = os.path.join(self.gadget_path, "sounds")
        
        self.setMouseTracking(True)
        self.setWindowTitle('Digital Gadget')
        self.resize(384, 191)

        self.player = VlcPlayer()
        self.assets: Dict[str, QPixmap] = {}
        self.digit_pixmaps: List[QPixmap] = []
        
        self._load_assets()

        self.timer_status = TimerStatus.RESET
        
        self.current_hour = 0
        self.current_minute = 0
        self.current_second = 0
        
        self.logic_timer = QTimer(self)
        self.logic_timer.timeout.connect(self._update_timer_state)
        self.logic_timer.start(1000)

        self.hovered_button: Optional[QImageButton] = None
        self.all_buttons: List[QImageButton] = []
        self._create_buttons()
        self._update_button_states()

    def _load_assets(self):
        asset_files = [
            "timer_panel.png",
            "button-increase.png", "button-increase-hover.png", "button-increase-disable.png",
            "button-decrease.png", "button-decrease-hover.png", "button-decrease-disable.png",
            "control-button-play.png", "control-button-play-hover.png", "control-button-play-disable.png",
            "control-button-pause.png", "control-button-pause-hover.png", "control-button-pause-disable.png",
            "control-button-stop.png", "control-button-stop-hover.png", "control-button-stop-disable.png",
        ]
        for i in range(10):
            asset_files.append(f"digital_number_{i}.png")

        for filename in asset_files:
            key = filename.split('.')[0]
            path = os.path.join(self.gadget_assets_path, filename)
            self.assets[key] = QPixmap(path)
        
        self.digit_pixmaps = [self.assets[f'digital_number_{i}'] for i in range(10)]

    def _create_buttons(self):
        self.btnIncreaseHour = QImageButton((43, 17), (45, 26),
            self.assets["button-increase"], self.assets["button-increase-hover"], self.assets["button-increase-disable"],
            callback=self.increaseHour)
        self.btnIncreaseMinute = QImageButton((170, 17), (45, 26),
            self.assets["button-increase"], self.assets["button-increase-hover"], self.assets["button-increase-disable"],
            callback=self.increaseMinute)
        self.btnIncreaseSecond = QImageButton((297, 17), (45, 26),
            self.assets["button-increase"], self.assets["button-increase-hover"], self.assets["button-increase-disable"],
            callback=self.increaseSecond)
        
        self.btnDecreaseHour = QImageButton((43, 147), (45, 26),
            self.assets["button-decrease"], self.assets["button-decrease-hover"], self.assets["button-decrease-disable"],
            callback=self.decreaseHour)
        self.btnDecreaseMinute = QImageButton((170, 147), (45, 26),
            self.assets["button-decrease"], self.assets["button-decrease-hover"], self.assets["button-decrease-disable"],
            callback=self.decreaseMinute)
        self.btnDecreaseSecond = QImageButton((297, 147), (45, 26),
            self.assets["button-decrease"], self.assets["button-decrease-hover"], self.assets["button-decrease-disable"],
            callback=self.decreaseSecond)

        self.btnStart = QImageButton((117, 161), (22, 22),
            self.assets["control-button-play"], self.assets["control-button-play-hover"], self.assets["control-button-play-disable"],
            callback=self.timer_start)
        self.btnPause = QImageButton((117, 161), (22, 22),
            self.assets["control-button-pause"], self.assets["control-button-pause-hover"], self.assets["control-button-pause-disable"],
            callback=self.timer_pause)
        self.btnStop = QImageButton((245, 161), (22, 22),
            self.assets["control-button-stop"], self.assets["control-button-stop-hover"], self.assets["control-button-stop-disable"],
            callback=self.timer_stop)
        
        self.all_buttons = [
            self.btnIncreaseHour, self.btnIncreaseMinute, self.btnIncreaseSecond,
            self.btnDecreaseHour, self.btnDecreaseMinute, self.btnDecreaseSecond,
            self.btnStart, self.btnPause, self.btnStop
        ]

    def _update_timer_state(self):
        if self.timer_status != TimerStatus.RUNNING:
            return

        total_seconds = self.current_hour * 3600 + self.current_minute * 60 + self.current_second
        if total_seconds > 0:
            total_seconds -= 1
            self.current_hour = total_seconds // 3600
            self.current_minute = (total_seconds % 3600) // 60
            self.current_second = total_seconds % 60
            #self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_ticking.wav"))
        else:
            self.timer_status = TimerStatus.RESET
            self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_alarm.wav"))
            self._update_button_states()
        
        self.update()

    def _update_button_states(self):
        is_reset_state = self.timer_status == TimerStatus.RESET
        
        for btn in [self.btnIncreaseHour, self.btnIncreaseMinute, self.btnIncreaseSecond,
                    self.btnDecreaseHour, self.btnDecreaseMinute, self.btnDecreaseSecond]:
            btn.isEnabled = is_reset_state

        self.btnStart.isVisible = (self.timer_status != TimerStatus.RUNNING)
        self.btnPause.isVisible = (self.timer_status == TimerStatus.RUNNING)
        
        if is_reset_state:
            self.current_hour = 0
            self.current_minute = 0
            self.current_second = 0

        self.update()

    # --- Event Handlers ---

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
    
    # --- Callback Methods ---
    def timer_start(self):
        total_seconds = self.current_hour * 3600 + self.current_minute * 60 + self.current_second
        if total_seconds <= 0:
            QMessageBox.warning(self, "Error", "You must set up a valid time!")
            return
            
        self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_setup.wav"))
        self.timer_status = TimerStatus.RUNNING
        self._update_button_states()

    def timer_pause(self):
        self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_setup.wav"))
        self.timer_status = TimerStatus.PAUSE
        self._update_button_states()

    def timer_stop(self):
        self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_setup.wav"))
        self.timer_status = TimerStatus.RESET
        self._update_button_states()

    def _adjust_time(self, unit: str, delta: int):
        self.player.playSound(os.path.join(self.gadget_sounds_path, "timer_setup.wav"))
        if unit == 'h':
            self.current_hour = max(0, min(99, self.current_hour + delta))
        elif unit == 'm':
            self.current_minute = max(0, min(59, self.current_minute + delta))
        elif unit == 's':
            self.current_second = max(0, min(59, self.current_second + delta))
        self.update()

    def increaseHour(self): self._adjust_time('h', 1)
    def increaseMinute(self): self._adjust_time('m', 1)
    def increaseSecond(self): self._adjust_time('s', 1)
    def decreaseHour(self): self._adjust_time('h', -1)
    def decreaseMinute(self): self._adjust_time('m', -1)
    def decreaseSecond(self): self._adjust_time('s', -1)

    # --- Painting ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.drawPixmap(self.rect(), self.assets["timer_panel"])
        
        self.render_digital(painter, self.current_hour, (14, 54), (48, 83))
        self.render_digital(painter, self.current_minute, (141, 54), (48, 83))
        self.render_digital(painter, self.current_second, (268, 54), (48, 83))
        
        for btn in self.all_buttons:
            btn.paint(painter)
            
        painter.end()

    def render_digital(self, painter: QPainter, value: int, pos: tuple[int, int], size: tuple[int, int]):
        gap = 7
        
        s_value = f"{value:02d}"
        
        digit1 = int(s_value[0])
        digit2 = int(s_value[1])
        
        rect = QRect(pos[0], pos[1], size[0], size[1])
        rect2 = QRect(pos[0] + size[0] + gap, pos[1], size[0], size[1])
        
        painter.drawPixmap(rect, self.digit_pixmaps[digit1])
        painter.drawPixmap(rect2, self.digit_pixmaps[digit2])


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Error: need to provide the gadget_path as argument")
        sys.exit(1)
    else:
        gadget_path_arg = sys.argv[1]
        
    app = QApplication(sys.argv)
    gadget = TimerGadget(gadget_path=gadget_path_arg)
    gadget.show()
    sys.exit(app.exec())