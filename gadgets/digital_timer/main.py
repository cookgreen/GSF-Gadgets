import sys
import os
from typing import Optional, Callable, Tuple, Any
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

# dynamic add GSF core lib into Python dir
from gsf.gadget_base import BaseGadget

TIMER_STATUS_RESET = 999
TIMER_STATUS_RUNNING = 900
TIMER_STATUS_PAUSE = 901

class QImageButton:
    def __init__(self,
                 pos: tuple[int, int], 
                 size: tuple[int, int], 
                 normal_image: QImage, 
                 hover_image: QImage,
                 disabled_image: QImage,
                 callback: Optional[Callable[..., None]]=None):
        self.pos = pos
        self.size = size
        
        self.normal_image = normal_image
        self.hover_image = hover_image
        self.disabled_image = disabled_image
        
        self.callback = callback
        
        self.hovered = False
        self.isEnabled = True
    
    def checkIsEnter(self, mousePosX, mousePosY):
        if mousePosX > self.pos[0] and mousePosX < self.pos[0] + self.size[0]:
            if mousePosY > self.pos[1] and mousePosY < self.pos[1] + self.size[1]:
                return True
        
        return False
    
    def mouseMove(self, mousePosX, mousePosY):
        if not self.isEnabled:
            return
        
        if self.checkIsEnter(mousePosX, mousePosY):
            self.hovered = True
        else:
            self.hovered = False
    
    def mousePress(self):
        if not self.isEnabled:
            return
        
        if self.callback and callable(self.callback):
            self.callback()
            
    def paint(self, painter: QPainter):
        target_rect = QRect(self.pos[0], self.pos[1], self.size[0], self.size[1])
        
        if not self.isEnabled:
            painter.drawImage(target_rect, self.disabled_image)
        else:
            if not self.hovered:
                painter.drawImage(target_rect, self.normal_image)
            else:
                painter.drawImage(target_rect, self.hover_image)
    
class TimerGadget(BaseGadget):
    def __init__(self, gadget_path):
        # must call parent class constructor
        super().__init__(gadget_path)
        
        self.setMouseTracking(True)
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        
        # --- specific logic ---
        self.setWindowTitle('Digital Gadget')
        self.resize(384, 191)
        
        self.timer_status = TIMER_STATUS_RESET
        self.hasReseted = True
        
        # --- load images ---
        self.timer_panel = QImage(os.path.join(self.gadget_assets_path, "timer_panel.png"))
        self.digitalNumber0 = QImage(os.path.join(self.gadget_assets_path, "digital_number_0.png"))
        self.digitalNumber1 = QImage(os.path.join(self.gadget_assets_path, "digital_number_1.png"))
        self.digitalNumber2 = QImage(os.path.join(self.gadget_assets_path, "digital_number_2.png"))
        self.digitalNumber3 = QImage(os.path.join(self.gadget_assets_path, "digital_number_3.png"))
        self.digitalNumber4 = QImage(os.path.join(self.gadget_assets_path, "digital_number_4.png"))
        self.digitalNumber5 = QImage(os.path.join(self.gadget_assets_path, "digital_number_5.png"))
        self.digitalNumber6 = QImage(os.path.join(self.gadget_assets_path, "digital_number_6.png"))
        self.digitalNumber7 = QImage(os.path.join(self.gadget_assets_path, "digital_number_7.png"))
        self.digitalNumber8 = QImage(os.path.join(self.gadget_assets_path, "digital_number_8.png"))
        self.digitalNumber9 = QImage(os.path.join(self.gadget_assets_path, "digital_number_9.png"))

        timer = QTimer(self)
        timer.timeout.connect(self.update) # update() will trigger paintEvent
        timer.start(1000)
        
        self.current_hour = 0
        self.current_minute = 0
        self.current_second = 0
        self.custom_sub_widgets = []
        
        self.btnIncreaseHour = QImageButton((43, 17), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-increase.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-disable.png")),
            callback=self.increaseHour)
        self.btnIncreaseMinute = QImageButton((170, 17), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-increase.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-disable.png")),
            callback=self.increaseMinute)
        self.btnIncreaseSecond = QImageButton((297, 17), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-increase.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-increase-disable.png")),
            callback=self.increaseSecond)
        
        self.btnDecreaseHour = QImageButton((43, 147), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-decrease.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-disable.png")),
            callback=self.decreaseHour)
        self.btnDecreaseMinute = QImageButton((170, 147), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-decrease.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-disable.png")),
            callback=self.decreaseMinute)
        self.btnDecreaseSecond = QImageButton((297, 147), (45, 26), 
            QImage(os.path.join(self.gadget_assets_path, "button-decrease.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-decrease-disable.png")),
            callback=self.decreaseSecond)
        
        self.btnStart = QImageButton((117, 161), (22, 22), 
            QImage(os.path.join(self.gadget_assets_path, "control-button-play.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-play-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-play-disable.png")),
            callback=self.timer_start)
        self.btnPause = QImageButton((117, 161), (22, 22), 
            QImage(os.path.join(self.gadget_assets_path, "control-button-pause.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-pause-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-pause-disable.png")),
            callback=self.timer_pause)
        self.btnStop = QImageButton((245, 161), (22, 22), 
            QImage(os.path.join(self.gadget_assets_path, "control-button-stop.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-stop-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "control-button-stop-disable.png")),
            callback=self.timer_stop)
        
        self.custom_sub_widgets.append(self.btnIncreaseHour)
        self.custom_sub_widgets.append(self.btnIncreaseMinute)
        self.custom_sub_widgets.append(self.btnIncreaseSecond)
        self.custom_sub_widgets.append(self.btnDecreaseHour)
        self.custom_sub_widgets.append(self.btnDecreaseMinute)
        self.custom_sub_widgets.append(self.btnDecreaseSecond)
        
        self.custom_sub_widgets.append(self.btnStart)
        self.custom_sub_widgets.append(self.btnPause)
        self.custom_sub_widgets.append(self.btnStop)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        mousePosX = event.pos().x()
        mousePosY = event.pos().y()
        
        for custom_sub_widget in self.custom_sub_widgets:
            custom_sub_widget.mouseMove(mousePosX, mousePosY)
            
        super().mouseMoveEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            mousePosX = event.pos().x()
            mousePosY = event.pos().y()
            
            for custom_sub_widget in self.custom_sub_widgets:
                if custom_sub_widget.checkIsEnter(mousePosX, mousePosY):
                    custom_sub_widget.mousePress()
                    return
                        
        super().mousePressEvent(event) # Call base class implementation
    
    def timer_start(self):
        if self.current_hour == 0 and self.current_minute == 0 and self.current_second == 0:
            msg_error = QMessageBox(self)
            msg_error.setWindowTitle("Error")
            msg_error.setText("You must setup a valid time!")
            msg_error.setIcon(QMessageBox.Icon.Warning)
            msg_error.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_error.exec()
            return
            
        self.timer_status = TIMER_STATUS_RUNNING
    
    def timer_pause(self):
        self.timer_status = TIMER_STATUS_PAUSE
    
    def timer_stop(self):
        self.timer_status = TIMER_STATUS_RESET
    
    def increaseHour(self):
        if self.current_hour < 59:
            self.current_hour = self.current_hour + 1
        
    def increaseMinute(self):
        if self.current_minute < 59:
            self.current_minute = self.current_minute + 1
        
    def increaseSecond(self):
        if self.current_second < 59:
            self.current_second = self.current_second + 1
        
    def decreaseHour(self):
        if self.current_hour > 0:
            self.current_hour = self.current_hour - 1
        
    def decreaseMinute(self):
        if self.current_minute > 0:
            self.current_minute = self.current_minute - 1
        
    def decreaseSecond(self):
        if self.current_second > 0:
            self.current_second = self.current_second - 1
        
    def paintEvent(self, event):
        """only care about how to paint，other are handled by base-class"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        target_rect = QRect(0, 0, 384, 191)
        painter.drawImage(target_rect, self.timer_panel)
        
        self.btnStop.paint(painter)
        
        if self.timer_status == TIMER_STATUS_RESET:
            self.btnStart.paint(painter)
            
            if (self.current_hour != 0 or self.current_minute != 0 or self.current_second != 0) and (not self.hasReseted):
                self.current_hour = 0
                self.current_minute = 0
                self.current_second = 0
                
                self.btnIncreaseHour.isEnabled = True
                self.btnIncreaseMinute.isEnabled = True
                self.btnIncreaseSecond.isEnabled = True
                self.btnDecreaseHour.isEnabled = True
                self.btnDecreaseMinute.isEnabled = True
                self.btnDecreaseSecond.isEnabled = True
                self.hasReseted = True
                
        elif self.timer_status == TIMER_STATUS_RUNNING:
            self.btnPause.paint(painter)
            self.hasReseted = False
                
            self.btnIncreaseHour.isEnabled = False
            self.btnIncreaseMinute.isEnabled = False
            self.btnIncreaseSecond.isEnabled = False
            self.btnDecreaseHour.isEnabled = False
            self.btnDecreaseMinute.isEnabled = False
            self.btnDecreaseSecond.isEnabled = False
            
            if self.current_second > 0:
                self.current_second = self.current_second - 1
            elif self.current_second == 0:
                if self.current_minute > 0:
                    self.current_minute = self.current_minute - 1
                    self.current_second = 59
                elif self.current_minute == 0:
                    if self.current_hour > 0:
                        self.current_hour = self.current_hour - 1
                        self.current_minute = 59
                        self.current_minute = 59
                    elif self.current_hour == 0:
                        msg_info = QMessageBox(self)
                        msg_info.setWindowTitle("Notice")
                        msg_info.setText("Time is up!")
                        msg_info.setIcon(QMessageBox.Icon.Information)
                        msg_info.setStandardButtons(QMessageBox.StandardButton.Ok)
                        msg_info.exec()
                        self.timer_status = TIMER_STATUS_RESET
        
        elif self.timer_status == TIMER_STATUS_PAUSE:
            self.btnStart.paint(painter)
                
            self.btnIncreaseHour.isEnabled = False
            self.btnIncreaseMinute.isEnabled = False
            self.btnIncreaseSecond.isEnabled = False
            self.btnDecreaseHour.isEnabled = False
            self.btnDecreaseMinute.isEnabled = False
            self.btnDecreaseSecond.isEnabled = False
        
        self.render_digitals(self.current_hour, painter, (14, 54), (48, 83), [7])
        self.render_digitals(self.current_minute, painter, (141, 54), (48, 83),[7])
        self.render_digitals(self.current_second, painter, (268, 54), (48, 83),[7])
        
        self.btnIncreaseHour.paint(painter)
        self.btnIncreaseMinute.paint(painter)
        self.btnIncreaseSecond.paint(painter)
        
        self.btnDecreaseHour.paint(painter)
        self.btnDecreaseMinute.paint(painter)
        self.btnDecreaseSecond.paint(painter)
        
        painter.end()
    
    def render_digitals(self, val, painter: QPainter, 
                        startPos: tuple[int, int], 
                        size: tuple[int, int], 
                        gap_list: list[int]
                        ):
        val_digitals_list = self.get_digits(val)
        val_digitals_num = len(val_digitals_list)
        
        if val_digitals_num == 1:
            target_rect = QRect(startPos[0], startPos[1], size[0], size[1])
            painter.drawImage(target_rect, self.digitalNumber0)
            
            target_rect = QRect(startPos[0] + size[0] + gap_list[0], startPos[1], size[0], size[1])
            painter.drawImage(target_rect, self.getImageByDigital(val_digitals_list[0]))
        else:
            posX = 0
            posY = 0
            for i, digit in enumerate(val_digitals_list):
                if i == 0:
                    posX = startPos[0]
                    posY = startPos[1]
                else:
                    posX = startPos[0] + size[0]*i + gap_list[i-1]
                target_rect = QRect(posX, posY, size[0], size[1])
                painter.drawImage(target_rect, self.getImageByDigital(digit))
            
    def getImageByDigital(self, digit):
        if digit == 0:
            return self.digitalNumber0
        elif digit == 1:
            return self.digitalNumber1
        elif digit == 2:
            return self.digitalNumber2
        elif digit == 3:
            return self.digitalNumber3
        elif digit == 4:
            return self.digitalNumber4
        elif digit == 5:
            return self.digitalNumber5
        elif digit == 6:
            return self.digitalNumber6
        elif digit == 7:
            return self.digitalNumber7
        elif digit == 8:
            return self.digitalNumber8
        elif digit == 9:
            return self.digitalNumber9
        
        return None
        
    def get_digits(self, number: int) -> list[int]:
        positive_num = abs(number)
        s_number = str(positive_num)
        digits = [int(digit) for digit in s_number]
        
        return digits

if __name__ == '__main__':
    # get gadget_path from command line
    if len(sys.argv) < 2:
        print("Error: need to provide the gadget_path as argument")
        sys.exit(1)
    
    gadget_path_arg = sys.argv[1]

    app = QApplication(sys.argv)
    
    gadget = TimerGadget(gadget_path=gadget_path_arg)
    gadget.show()
    sys.exit(app.exec())