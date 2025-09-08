import json
import random
import vlc
import time
import threading

class VlcPlayer():
    def __init__(self):
        self.player_worker = None
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
    
    def playSound(self, url):
        if self.vlc_player == None:
            self.vlc_instance = vlc.Instance()
            self.vlc_player = vlc_instance.media_player_new()
            
        if self.vlc_player.is_playing():
            self.vlc_player.stop()
        else:
            self.vlc_player.play()
        
        self.player_worker = threading.Thread(target=self.playSound_worker, kwargs={"url": url})
        self.player_worker.start()
            
    def playSound_worker(self, url):
        media = self.vlc_instance.media_new(url)
        self.vlc_player.set_media(media)
        
        # Start playback
        self.vlc_player.play()