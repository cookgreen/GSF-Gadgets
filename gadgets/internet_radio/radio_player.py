import json
import random
import vlc
import time
import threading

class RadioPlayer():
    def __init__(self):
        self.player_worker = None
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
    
    def playFM(self, radio_data):
        url = radio_data['url']
        
        if self.vlc_player == None:
            self.vlc_instance = vlc.Instance()
            self.vlc_player = vlc_instance.media_player_new()
            
        if self.vlc_player.is_playing():
            self.vlc_player.stop()
        else:
            self.vlc_player.play()
        
        self.player_worker = threading.Thread(target=self.playerFM_worker, kwargs={"url": url})
        self.player_worker.start()
            
    def playerFM_worker(self, url):
        media = self.vlc_instance.media_new(url)
        self.vlc_player.set_media(media)
        
        # Start playback
        self.vlc_player.play()
        
        # Keep the script running while the stream plays
        # (You might want a more sophisticated loop for user interaction or error handling)
        try:
            while self.vlc_player.is_playing():
                time.sleep(1) # Sleep to prevent busy-waiting
        except KeyboardInterrupt:
            self.player.stop()
            print("Playback stopped.")
            
    def pauseFM(self):
        self.vlc_player.pause()
        
    def stopFM(self):
        self.vlc_player.stop()