# google_test.py

import json
from map_servers.google_server import (
    search_nearby,
    get_place_details,
    maps_geocode,
    maps_reverse_geocode,
    maps_distance_matrix,
    maps_directions,
    maps_elevation,
    maps_autocomplete,
)

def pretty(x):
    print(json.dumps(x, indent=2))


print("="*60)
print("TEST 1: Autocomplete")
print("="*60)
pretty(
    maps_autocomplete("lond")
)

print("="*60)
print("TEST 2: Geocode → Coordinates")
print("="*60)
pretty(
    maps_geocode("London, UK")
)

print("="*60)
print("TEST 3: Reverse Geocode → Address")
print("="*60)
pretty(
    maps_reverse_geocode(51.5074, -0.1278)
)

print("="*60)
print("TEST 4: Nearby Search (restaurants)")
print("="*60)
# Using coordinates of central London
pretty(
    search_nearby(
        location="51.5074,-0.1278",
        radius=1500,
        type="restaurant",
        min_rating=4.2
    )
)

print("="*60)
print("TEST 5: Place Details")
print("="*60)
# Replace with real place_id from nearby search
pretty(
    get_place_details("ChIJr_4cVy8FdkgRIrNbO93eUFM")
)

print("="*60)
print("TEST 6: Distance Matrix")
print("="*60)
pretty(
    maps_distance_matrix(
        origins=["London Eye"],
        destinations=["Buckingham Palace"],
        mode="walking"
    )
)

print("="*60)
print("TEST 7: Directions")
print("="*60)
pretty(
    maps_directions(
        origin="London Eye",
        destination="Buckingham Palace",
        mode="walking"
    )
)

print("="*60)
print("TEST 8: Elevation")
print("="*60)
pretty(
    maps_elevation(["51.5074,-0.1278"])
)
