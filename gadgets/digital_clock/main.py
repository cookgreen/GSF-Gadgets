import sys
import os
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

# dynamic add GSF core lib into Python dir
from gsf.gadget_base import BaseGadget

class ClockGadget(BaseGadget):
    def __init__(self, gadget_path):
        # must call parent class constructor
        super().__init__(gadget_path)
        
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        
        # --- specific logic ---
        self.resize(200, 200)
        self.setWindowTitle('Digital Gadget')
        self.setGeometry(100, 100, 800, 800)
        
        # --- load images ---
        self.clock_panel = QImage(os.path.join(self.gadget_assets_path, "clock_panel.png"))
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

    def paintEvent(self, event):
        """only care about how to paint，other are handled by base-class"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        target_rect = QRect(0, 0, 384, 191)
        painter.drawImage(target_rect, self.clock_panel)
        
        currentDate = QDate.currentDate()
        year = currentDate.year()
        month = currentDate.month()
        day = currentDate.day()
        self.render_digitals(year, painter, (42, 23), (12, 21), [3, 3, 3])
        self.render_digitals(month, painter, (104, 23), (12, 21), [3])
        self.render_digitals(day, painter, (138, 23), (12, 21), [3])
        
        currentTime = QTime.currentTime()
        hour = currentTime.hour()
        minute = currentTime.minute()
        self.render_digitals(hour, painter, (41, 65), (66, 112), [7])
        self.render_digitals(minute, painter, (213, 65), (66, 112),[7])
        
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
    
    gadget = ClockGadget(gadget_path=gadget_path_arg)
    gadget.show()
    sys.exit(app.exec())