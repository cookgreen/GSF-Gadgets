import vlc
import ctypes
import pyaudio
from PySide6.QtCore import QObject, Signal

AUDIO_FORMAT = "S16N"
CHANNELS = 2
RATE = 44100

# 回调函数是正确的，保持不变
@vlc.CallbackDecorators.AudioPlayCb
def audio_play_cb(opaque, data, samples, pts):
    try:
        if not opaque: return
        py_obj_ptr = ctypes.cast(opaque, ctypes.POINTER(ctypes.py_object))
        player_instance = py_obj_ptr.contents.value
        
        audio_data_ptr = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint8))
        audio_buffer = ctypes.string_at(audio_data_ptr, samples * CHANNELS * 2)
        
        # --- 核心修改 ---
        # 1. 将音频数据写入声卡
        player_instance.play_audio_chunk(audio_buffer)
        
        # 2. 将音频数据发射给 visualizer
        player_instance.audio_data_ready.emit(audio_buffer)
        # --- 修改结束 ---
        
    except Exception as e:
        print(f"!!! EXCEPTION IN VLC CALLBACK: {e}")

class RadioPlayer(QObject):
    audio_data_ready = Signal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
        
        initial_volume = 100
        self.vlc_player.audio_set_volume(initial_volume)
        
        self.self_ptr = ctypes.py_object(self)
        
        self.p = pyaudio.PyAudio()
        self.audio_stream = None
        
        self.setup_audio_callbacks()
    
    def open_audio_stream(self):
        """当播放开始时，打开一个 PyAudio 输出流"""
        if self.audio_stream:
            self.close_audio_stream()
        
        try:
            self.audio_stream = self.p.open(format=pyaudio.paInt16, # paInt16 对应 S16N
                                              channels=CHANNELS,
                                              rate=RATE,
                                              output=True)
            print("--- PyAudio stream opened ---")
        except Exception as e:
            print(f"!!! Failed to open PyAudio stream: {e}")
            self.audio_stream = None

    def close_audio_stream(self):
        """当播放停止时，关闭 PyAudio 输出流"""
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None
            print("--- PyAudio stream closed ---")

    def play_audio_chunk(self, audio_data: bytes):
        """将音频数据块写入 PyAudio 流"""
        if self.audio_stream and self.audio_stream.is_active():
            try:
                self.audio_stream.write(audio_data)
            except Exception as e:
                print(f"Error writing to PyAudio stream: {e}")
    
    def setup_audio_callbacks(self):
        self.vlc_player.audio_set_callbacks(
            play=audio_play_cb,
            pause=None, resume=None, flush=None, drain=None,
            opaque=ctypes.byref(self.self_ptr)
        )
        self.vlc_player.audio_set_format(AUDIO_FORMAT, RATE, CHANNELS)
    
    def playFM(self, radio_data):
        try:
            self.open_audio_stream() # 在播放前打开音频流
            url = radio_data['url_resolved'] or radio_data['url']
            if not url:
                print("Error: Radio data has no valid URL.")
                return

            print(f"Attempting to play URL: {url}")
            
            media = self.vlc_instance.media_new(url)
            
            self.vlc_player.set_media(media)
            
            self.vlc_player.play()

        except Exception as e:
            print(f"Error in playFM: {e}")
            
    def pauseFM(self):
        if self.vlc_player.is_playing():
            self.vlc_player.pause()
        
    def stopFM(self):
        self.close_audio_stream() # 在停止后关闭音频流
        if self.vlc_player.get_media():
            self.vlc_player.stop()
            
    def on_media_parsed(self, event):
        media = self.vlc_player.get_media()
        if media:
            print(f">>> VLC Event: Media parsed. Title: {media.get_meta(vlc.Meta.Title)}, Artist: {media.get_meta(vlc.Meta.Artist)}")
            
    def is_playing(self):
        return self.vlc_player.is_playing()
        
    def __del__(self):
        # 确保在对象销毁时清理 PyAudio
        self.close_audio_stream()
        self.p.terminate()
        print("--- PyAudio terminated ---")