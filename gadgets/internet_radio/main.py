import sys
import os
from typing import Optional, Callable, Tuple, Any
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

# dynamic add GSF core lib into Python dir
from gsf.gadget_base import BaseGadget

from radio_browser_api import *
from radio_player import *

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
    
class InternetRadioGadget(BaseGadget):
    def __init__(self, gadget_path):
        # must call parent class constructor
        super().__init__(gadget_path)
        
        self.setMouseTracking(True)
        self.gadget_path = gadget_path
        self.gadget_assets_path = os.path.join(self.gadget_path, "assets")
        self.api = RadioBrowserApi()
        self.status_report = ""
        self.current_playing_index = 0
        self.player = RadioPlayer()
        
        self.initization()
        
        # --- specific logic ---
        self.setWindowTitle('Internet Radio')
        self.resize(384, 174)
        
        self.hasReseted = True

        timer = QTimer(self)
        timer.timeout.connect(self.update) # update() will trigger paintEvent
        timer.start(1000)
        self.custom_sub_widgets = []
        
        # --- load images ---
        self.main_panel = QImage(os.path.join(self.gadget_assets_path, "main_panel.png"))
        
        self.btnPlay = QImageButton((168, 124), (48, 48), 
            QImage(os.path.join(self.gadget_assets_path, "button-play.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-play-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-play-disable.png")),
            callback=self.playFM)
        self.btnPlay.isEnabled = False
        
        self.btnPause = QImageButton((168, 124), (48, 48), 
            QImage(os.path.join(self.gadget_assets_path, "button-pause.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-pause-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-pause-disable.png")),
            callback=self.pauseFM)
        self.btnPause.isEnabled = False
        
        self.btnRandom = QImageButton((76, 131), (34, 34), 
            QImage(os.path.join(self.gadget_assets_path, "button-random.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-random-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-random-disable.png")),
            callback=self.randomPlayFM)
        self.btnRandom.isEnabled = False
        
        self.btnStop = QImageButton((275, 131), (34, 34), 
            QImage(os.path.join(self.gadget_assets_path, "button-stop.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-stop-hover.png")),
            QImage(os.path.join(self.gadget_assets_path, "button-stop-disable.png")),
            callback=self.stopFM)
        self.btnStop.isEnabled = False
            
        self.custom_sub_widgets.append(self.btnRandom)
        self.custom_sub_widgets.append(self.btnStop)
        self.custom_sub_widgets.append(self.btnPlay)
    
    def initization_worker(self):
        while True:
            if len(self.api.radio_data) > 0:
                break
                
        self.status_report = "Initialization Completed"
        
        time.sleep(1)
        
        self.status_report = "Ready"
        
        self.randomPlayFM()
        
        self.btnPlay.isEnabled = True
        self.btnPause.isEnabled = True
        self.btnRandom.isEnabled = True
        self.btnStop.isEnabled = True
    
    def initization(self):
        self.api.read_data_all()
        
        self.status_report = "Initializing the data"
            
        self.main_worker = threading.Thread(target=self.initization_worker)
        self.main_worker.start()
    
    def playFM(self):
        radio = self.api.radio_data[self.current_playing_index]
        
        self.status_report = "Playing...";
        self.player.playFM(radio)
    
    def pauseFM(self):
        self.status_report = "Paused";
        self.player.pauseFM()
        
    def randomPlayFM(self):
        self.current_playing_index = random.randint(0, len(self.api.radio_data) - 1)
        radio = self.api.radio_data[self.current_playing_index]
        
        self.status_report = "Playing...";
        
        self.player.playFM(radio)
    
    def stopFM(self):
        self.status_report = "Ready";
        self.player.stopFM()
    
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
        
    def paintEvent(self, event):
        """only care about how to paint，other are handled by base-class"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        target_rect = QRect(0, 0, 384, 178)
        painter.drawImage(target_rect, self.main_panel)
        
        self.btnRandom.paint(painter)
        self.btnStop.paint(painter)
        
        if self.player.vlc_player.is_playing():
            self.btnPause.paint(painter)
            
            if self.btnPause not in self.custom_sub_widgets:
                self.custom_sub_widgets.append(self.btnPause)
            if self.btnPlay in self.custom_sub_widgets:
                self.custom_sub_widgets.remove(self.btnPlay)
        else:
            self.btnPlay.paint(painter)
            
            if self.btnPlay not in self.custom_sub_widgets:
                self.custom_sub_widgets.append(self.btnPlay)
            if self.btnPause in self.custom_sub_widgets:
                self.custom_sub_widgets.remove(self.btnPause)
        
        painter.setFont(QFont("Arial", 15)) # Set font family and size
        painter.setPen(Qt.GlobalColor.green) # Set text color to blue
        painter.drawText(21, 40, self.status_report)
        
        painter.end()

if __name__ == '__main__':
    # get gadget_path from command line
    if len(sys.argv) < 2:
        print("Error: need to provide the gadget_path as argument")
        sys.exit(1)
    
    gadget_path_arg = sys.argv[1]

    app = QApplication(sys.argv)
    
    gadget = InternetRadioGadget(gadget_path=gadget_path_arg)
    gadget.show()
    sys.exit(app.exec())