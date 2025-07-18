import json
import random
import vlc
import time
import threading
from urllib.request import *

CURRENT_RADIO_INDEX = 0
RADIO_DATA_ALL = []
lock = threading.Lock()
vlc_instance = None
vlc_player = None
player_worker = None

def read_data(offset=0, limit=500):
    result = urlopen("https://de2.api.radio-browser.info/json/stations/search?offset=0&limit=500&hidebroken=true&has_geo_info=true&order=clickcount&reverse=true&fields=name,url_resolved,url,favicon,countrycode,state,city,stationuuid,geo_lat,geo_long,tags")

    data_list = json.loads(result.read())
    return data_list
    
def read_data_worker(offset, limit):
    global RADIO_DATA_ALL
    try:
        data_list = read_data(offset)
        with lock:
            RADIO_DATA_ALL = RADIO_DATA_ALL + data_list
    except:
        pass
    
def read_data_all_worker():
    offset = 0
    data_list = read_data()
    data_len = len(data_list)
    
    for i in range(16):
        offset = offset + 500
        worker = threading.Thread(
            target=read_data_worker, 
            kwargs={"offset": offset, "limit": 500})
        worker.start()
    
    
def read_data_all():
    main_worker = threading.Thread(
                target=read_data_all_worker)
    main_worker.start()
    
def playFM(url):
    global player_worker
    global vlc_player
    global vlc_instance
    
    if vlc_player == None:
        vlc_instance = vlc.Instance()
        vlc_player = vlc_instance.media_player_new()
        
    if vlc_player.is_playing():
        vlc_player.stop()
    else:
        vlc_player.play()
        
    player_worker = threading.Thread(target=playerFM_worker, kwargs={"url": url})
    player_worker.start()
        
def playerFM_worker(url):
    global vlc_player
    
    print(url)
    media = vlc_instance.media_new(url)
    vlc_player.set_media(media)
    
    # Start playback
    vlc_player.play()
    
    # Keep the script running while the stream plays
    # (You might want a more sophisticated loop for user interaction or error handling)
    try:
        while vlc_player.is_playing():
            time.sleep(1) # Sleep to prevent busy-waiting
    except KeyboardInterrupt:
        player.stop()
        print("Playback stopped.")
        
def pauseFM():
    global vlc_player
    vlc_player.pause()
    
def print_pause_options(radio_data):
    pauseFM()
    
    print(f"[Status] paused")
    
    print("1. Resume")
    print("2. Random Play Next")
    
    input_str = input("Enter your choice(1-4):")
    choice = int(input_str)
    
    if choice == 1:
        print_play_options(radio_data)
    
    elif choice == 2:
        CURRENT_RADIO_INDEX = random.randint(0, len(RADIO_DATA_ALL) - 1)
        radio_new_data =  RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(radio_new_data)
        
    else:
        print("[Status] Please select a valid choice!")
        print_pause_options()
        
def print_play_options(radio_data):
    
    print(f"[Status] Playing {radio_data['name']}...")
    playFM(radio_data['url'])
    
    print("1. Pause")
    print("2. Random Play Next")
    print("3. Play Previous")
    print("4. Play Next")
    print("5. Stop")
    
    input_str = input("Enter your choice(1-4):")
    choice = int(input_str)
    
    if choice == 1:
        print_pause_options(radio_data)
    
    elif choice == 2:
        CURRENT_RADIO_INDEX = random.randint(0, len(RADIO_DATA_ALL) - 1)
        radio_new_data =  RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(radio_new_data)
        
    elif choice == 3:
        CURRENT_RADIO_INDEX = get_index_by_uuid(radio_data['stationuuid'])
        if CURRENT_RADIO_INDEX > 0:
            CURRENT_RADIO_INDEX = CURRENT_RADIO_INDEX - 1
        
        radio_new_data =  RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(radio_new_data)
        
    elif choice == 4:
        CURRENT_RADIO_INDEX = get_index_by_uuid(radio_data['stationuuid'])
        if CURRENT_RADIO_INDEX < len(RADIO_DATA_ALL) - 1:
            CURRENT_RADIO_INDEX = CURRENT_RADIO_INDEX + 1
            
        radio_new_data =  RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(radio_new_data)
        
    elif choice == 5:
        vlc_player.stop()
        print_choice()
        
    else:
        print("[Status] Please select a valid choice!")
        print_choice()

def print_choice():
    print("=================Internet Radio================")
    print("1. Random Play")
    print("2. Play First")
    print("3. Play Last")
    print("4. Exit")
    
    input_str = input("Enter your choice(1-5):")
    choice = int(input_str)
    
    if choice == 1:
        CURRENT_RADIO_INDEX = random.randint(0, len(RADIO_DATA_ALL) - 1)
        uuid = RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(uuid)
    
    elif choice == 2:
        CURRENT_RADIO_INDEX = 0
        uuid = RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(uuid)
    
    elif choice == 3:
        CURRENT_RADIO_INDEX = len(RADIO_DATA_ALL) - 1
        uuid = RADIO_DATA_ALL[CURRENT_RADIO_INDEX]
        print_play_options(uuid)
        
    elif choice == 4:
        return
        
    else:
        print("[Status] Please select a valid choice!")
        print_choice()

def get_index_by_uuid(uuid):
    for i, data in enumerate(RADIO_DATA_ALL):
        if data['stationuuid'] == uuid:
            return i

def main():
    global CURRENT_RADIO_INDEX
    
    urls = []
    read_data_all()
    
    print("[Status]: Initializing the data.....")
    
    while True:
        if len(RADIO_DATA_ALL) > 0:
            break
            
    print("[Status]: Initialization Completed!")
    
    print_choice()

if __name__ == '__main__':
    main()
