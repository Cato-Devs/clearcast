"""The 23 locations ClearCast serves: 17 Nairobi constituencies and 6 other towns.

Constituency coordinates are the centre of each boundary, printed by
tools/build_nairobi_boundaries.py. The towns are the training locations outside Nairobi.
"""
from training.locations import LOCATIONS as TRAINING_LOCATIONS

NAIROBI_CONSTITUENCIES = [
    {"name": "Westlands", "lat": -1.23839, "lon": 36.78838},
    {"name": "Dagoretti North", "lat": -1.27867, "lon": 36.77928},
    {"name": "Dagoretti South", "lat": -1.28245, "lon": 36.71497},
    {"name": "Lang'ata", "lat": -1.35428, "lon": 36.80480},
    {"name": "Kibra", "lat": -1.30331, "lon": 36.78683},
    {"name": "Roysambu", "lat": -1.20294, "lon": 36.88362},
    {"name": "Kasarani", "lat": -1.24937, "lon": 37.00815},
    {"name": "Ruaraka", "lat": -1.24408, "lon": 36.87892},
    {"name": "Embakasi South", "lat": -1.32909, "lon": 36.87784},
    {"name": "Embakasi North", "lat": -1.24732, "lon": 36.89730},
    {"name": "Embakasi Central", "lat": -1.26687, "lon": 36.91630},
    {"name": "Embakasi East", "lat": -1.30602, "lon": 36.93690},
    {"name": "Embakasi West", "lat": -1.27113, "lon": 36.88904},
    {"name": "Makadara", "lat": -1.29533, "lon": 36.86820},
    {"name": "Kamukunji", "lat": -1.27401, "lon": 36.85713},
    {"name": "Starehe", "lat": -1.29003, "lon": 36.83470},
    {"name": "Mathare", "lat": -1.25834, "lon": 36.86025},
]

OTHER_TOWNS = [loc for loc in TRAINING_LOCATIONS if loc["name"] != "Nairobi"]

LOCATIONS = {loc["name"]: loc for loc in NAIROBI_CONSTITUENCIES + OTHER_TOWNS}
