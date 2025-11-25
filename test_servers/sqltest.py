import sys 
sys.path.insert(0, "..")
from map_servers.hotelbeds_store import load_hotel_search


data = load_hotel_search(2, db_path="../databases/hotelbeds.sqlite")           # latest search
# or load_hotel_search(search_id=1)
print(data)
print(len(data["hotels"]))