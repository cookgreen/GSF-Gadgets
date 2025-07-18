import httplib

class RadioBrowserApi:
    def __init__(self):
        self.radio_data = {}
    
    def get_data_all(offset=0, limit=500):
        result = urlopen(f"https://de2.api.radio-browser.info/json/stations/search?offset={offset}&limit={limit}&hidebroken=true&has_geo_info=true&order=clickcount&reverse=true&fields=name,url_resolved,url,favicon,countrycode,state,city,stationuuid,geo_lat,geo_long,tags")
        
        self.radio_data.append()
        
        return get_data_all(offset+limit, limit)
    
    def get_data(offset=0, limit=500):
        result = urlopen(f"https://de2.api.radio-browser.info/json/stations/search?offset={offset}&limit={limit}&hidebroken=true&has_geo_info=true&order=clickcount&reverse=true&fields=name,url_resolved,url,favicon,countrycode,state,city,stationuuid,geo_lat,geo_long,tags")
        return result