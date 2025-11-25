

from __future__ import annotations

import os
import sys
from pprint import pprint
from typing import Dict, Any

# Allow running from test_servers/
sys.path.insert(0, "..")

from map_servers.hotelbeds_server import get_hotel_images_impl
from map_servers.hotelbeds_store import save_hotel_images

codes = [461452, 273049]
res = get_hotel_images_impl(codes)
if not res.get("error"):
    save_hotel_images(res["hotels"])
    print("saved images for", list(res["hotels"].keys()))
