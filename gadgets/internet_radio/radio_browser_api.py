import json
import time
import threading
from urllib.request import *

lock = threading.Lock()

class RadioBrowserApi:
    def __init__(self):
        self.radio_data = []

    def read_data(self, offset=0, limit=500):
        result = urlopen("https://de2.api.radio-browser.info/json/stations/search?offset=0&limit=500&hidebroken=true&has_geo_info=true&order=clickcount&reverse=true&fields=name,url_resolved,url,favicon,countrycode,state,city,stationuuid,geo_lat,geo_long,tags")
    
        data_list = json.loads(result.read())
        return data_list
    
    def read_data_worker(self, offset, limit):
        try:
            data_list = self.read_data(offset)
            with lock:
                self.radio_data = self.radio_data + data_list
        except Exception as e:
            print(e)
        
    def read_data_all_worker(self):
        offset = 0
        
        for i in range(16):
            worker = threading.Thread(
                target=self.read_data_worker, 
                kwargs={"offset": offset, "limit": 500})
            worker.start()
            
            offset = offset + 500
        
    def read_data_all(self):
        main_worker = threading.Thread(
                    target=self.read_data_all_worker)
        main_worker.start()