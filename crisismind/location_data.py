"""Generate location-aware contextual data for any searched location.

Instead of always returning hardcoded Raipur data, this module creates
plausible region names, shelters, hospitals, schools, hazard zones,
and emergency contacts that reflect the *actual* location being analysed.

A deterministic hash of the location name seeds every random choice so that
re-analysing the same city produces identical results.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_location_dataset(
    location_name: str,
    disaster_type: str,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Return a full dataset dict shaped like ``scenarios.json`` but with
    content dynamically tailored to *location_name* and *disaster_type*.
    """
    rng = _seeded_rng(location_name)
    country_code = _guess_country(location_name)
    short_name = _short_location(location_name)

    regions = _generate_regions(rng, short_name, location_name)
    roads = _generate_roads(rng, short_name)
    safe_zones = _generate_safe_zones(rng, short_name, country_code)
    hospitals = _generate_hospitals(rng, short_name)
    schools = _generate_schools(rng, short_name)
    hazard_templates = _generate_hazard_templates(rng, disaster_type, short_name)
    contacts = _generate_emergency_contacts(country_code, short_name)
    checklist = _generate_supply_checklist(disaster_type)
    resources = _generate_resources(rng)

    return {
        "scenarios": [],
        "regions": regions,
        "roads": roads,
        "safe_zones": safe_zones,
        "hospitals": hospitals,
        "schools": schools,
        "hazard_templates": hazard_templates,
        "emergency_contacts": contacts,
        "supply_checklist": checklist,
        "resources": resources,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seeded_rng(location_name: str) -> random.Random:
    digest = hashlib.sha256(location_name.lower().encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _short_location(location_name: str) -> str:
    """Extract a short usable city/region name."""
    parts = [p.strip() for p in location_name.split(",")]
    return parts[0] if parts else location_name


def _guess_country(location_name: str) -> str:
    """Best-effort country code from the location string."""
    name_lower = location_name.lower()
    mapping = {
        "india": "IN", "japan": "JP", "usa": "US", "united states": "US",
        "philippines": "PH", "bangladesh": "BD", "indonesia": "ID",
        "china": "CN", "mexico": "MX", "brazil": "BR", "australia": "AU",
        "uk": "GB", "united kingdom": "GB", "canada": "CA", "france": "FR",
        "germany": "DE", "italy": "IT", "spain": "ES", "turkey": "TR",
        "pakistan": "PK", "nigeria": "NG", "south africa": "ZA",
        "florida": "US", "california": "US", "texas": "US", "new york": "US",
        "tokyo": "JP", "osaka": "JP", "mumbai": "IN", "delhi": "IN",
        "kolkata": "IN", "chennai": "IN", "manila": "PH", "miami": "US",
        "london": "GB", "paris": "FR", "berlin": "DE", "sydney": "AU",
        "dhaka": "BD", "jakarta": "ID", "bangkok": "TH", "thailand": "TH",
        "vietnam": "VN", "nepal": "NP", "sri lanka": "LK",
        "korea": "KR", "south korea": "KR",
    }
    for key, code in mapping.items():
        if key in name_lower:
            return code
    return "XX"


# ---------------------------------------------------------------------------
# Region generator
# ---------------------------------------------------------------------------

_REGION_POOL = {
    "generic": [
        "Central District", "North Quarter", "South Ward", "East End",
        "West Bank", "Old Town", "New Town", "Industrial Zone",
        "Market District", "Riverside", "Hilltop", "Lakeside",
        "University Area", "Station Road Area", "Port District",
    ],
    "JP": [
        "Chiyoda", "Minato", "Shibuya", "Shinjuku", "Sumida",
        "Arakawa", "Koto", "Setagaya", "Meguro", "Nerima",
    ],
    "IN": [
        "Civil Lines", "Sadar Bazar", "Lal Darwaza", "Station Road",
        "Nehru Nagar", "Gandhi Chowk", "Indira Colony", "Subhash Ward",
        "Rajendra Nagar", "Ambedkar Colony",
    ],
    "PH": [
        "Ermita", "Intramuros", "Tondo", "Sampaloc", "Binondo",
        "Quiapo", "San Miguel", "Malate", "Pandacan", "Santa Cruz",
    ],
    "US": [
        "Downtown", "Midtown", "Uptown", "Westside", "Eastside",
        "Bayfront", "Harbor District", "Coral Way", "Brickell",
        "Overtown", "Wynwood", "Little River",
    ],
}


def _generate_regions(rng: random.Random, short_name: str, full_name: str) -> list[dict[str, Any]]:
    country = _guess_country(full_name)
    pool = list(_REGION_POOL.get(country, _REGION_POOL["generic"]))
    rng.shuffle(pool)
    count = rng.randint(5, 7)
    chosen = pool[:count]
    regions = []
    for i, name in enumerate(chosen):
        cx = rng.randint(14, 86)
        cy = rng.randint(16, 82)
        pop = rng.randint(18000, 55000)
        w = rng.randint(14, 24)
        h = rng.randint(12, 20)
        regions.append({
            "name": name,
            "population": pop,
            "center": {"x": cx, "y": cy},
            "bounds": {
                "x": max(2, cx - w // 2),
                "y": max(2, cy - h // 2),
                "width": w,
                "height": h,
            },
        })
    return regions


# ---------------------------------------------------------------------------
# Roads
# ---------------------------------------------------------------------------

def _generate_roads(rng: random.Random, short_name: str) -> list[dict[str, Any]]:
    road_names = [
        f"{short_name} Main Road", f"{short_name} Ring Road",
        "Airport Connector", "National Highway Link",
    ]
    roads = []
    for name in road_names[:3]:
        roads.append({
            "name": name,
            "path": [
                {"x": rng.randint(5, 20), "y": rng.randint(20, 75)},
                {"x": rng.randint(75, 94), "y": rng.randint(20, 75)},
            ],
        })
    return roads


# ---------------------------------------------------------------------------
# Safe zones / shelters
# ---------------------------------------------------------------------------

_SHELTER_TYPES = ["Shelter", "Relief Camp", "Safe Assembly", "Transit Shelter"]

_SHELTER_PREFIXES = {
    "generic": ["Community Hall", "Sports Complex", "Convention Center", "Transit School", "Assembly Ground"],
    "JP": ["Civic Arena", "Community Center", "Sports Dome", "Cultural Hall", "Gymnasium"],
    "IN": ["Indoor Stadium", "Convention Hall", "Assembly Ground", "Community Center", "Sports Complex"],
    "PH": ["Covered Court", "Barangay Hall", "Sports Arena", "Evacuation Center", "Community Gym"],
    "US": ["Convention Center", "Community Center", "High School Gym", "Sports Arena", "Civic Auditorium"],
}


def _generate_safe_zones(rng: random.Random, short_name: str, country: str) -> list[dict[str, Any]]:
    prefixes = _SHELTER_PREFIXES.get(country, _SHELTER_PREFIXES["generic"])
    zones = []
    for i, prefix in enumerate(prefixes):
        cap = rng.randint(600, 1800)
        zones.append({
            "id": f"shelter-{i + 1}",
            "name": f"{short_name} {prefix}",
            "address": f"Zone {i + 1}, {short_name}",
            "zone_type": _SHELTER_TYPES[i % len(_SHELTER_TYPES)],
            "capacity": cap,
            "available_capacity": rng.randint(cap // 3, cap),
            "contact": _fake_phone(country, rng),
            "location": {"x": rng.randint(8, 92), "y": rng.randint(8, 92)},
            "facilities": rng.sample(
                ["medical desk", "charging station", "dry ration", "water purification",
                 "ambulance bay", "family enclosure", "shade tents", "first aid",
                 "generator backup", "community kitchen", "mobile toilets"],
                k=3,
            ),
        })
    return zones


# ---------------------------------------------------------------------------
# Hospitals & schools
# ---------------------------------------------------------------------------

def _generate_hospitals(rng: random.Random, short_name: str) -> list[dict[str, Any]]:
    names = [
        f"{short_name} General Hospital",
        f"{short_name} District Hospital",
        f"{short_name} Medical Center",
        f"{short_name} Community Health Centre",
    ]
    return [
        {"name": n, "location": {"x": rng.randint(12, 85), "y": rng.randint(12, 85)}}
        for n in names
    ]


def _generate_schools(rng: random.Random, short_name: str) -> list[dict[str, Any]]:
    names = [
        f"{short_name} Public School",
        f"{short_name} Higher Secondary",
        f"{short_name} Girls School",
        f"{short_name} Model Academy",
    ]
    return [
        {"name": n, "location": {"x": rng.randint(12, 85), "y": rng.randint(12, 85)}}
        for n in names
    ]


# ---------------------------------------------------------------------------
# Hazard templates
# ---------------------------------------------------------------------------

_HAZARD_LABELS = {
    "flood": [
        {"name_tpl": "{loc} River Belt", "note": "River swell and low-lying inundation risk."},
        {"name_tpl": "{loc} Underpass Zone", "note": "Urban flash flooding and drainage overflow."},
        {"name_tpl": "{loc} Channel District", "note": "Rapid waterlogging around feeder roads."},
    ],
    "cyclone": [
        {"name_tpl": "{loc} Wind Corridor", "note": "High wind gust corridor with structural debris risk."},
        {"name_tpl": "{loc} Coastal Strip", "note": "Storm surge backflow and transport disruption."},
    ],
    "heatwave": [
        {"name_tpl": "{loc} Dense Core", "note": "Urban heat island with critical exposure."},
        {"name_tpl": "{loc} Industrial Belt", "note": "Extreme radiant heat and air-quality stress."},
    ],
}


def _generate_hazard_templates(
    rng: random.Random, disaster_type: str, short_name: str,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for dtype, templates in _HAZARD_LABELS.items():
        hazards = []
        for tpl in templates:
            hazards.append({
                "name": tpl["name_tpl"].format(loc=short_name),
                "center": {"x": rng.randint(18, 75), "y": rng.randint(18, 75)},
                "base_radius": rng.randint(9, 18),
                "radius_factor": rng.randint(5, 10),
                "note": tpl["note"],
            })
        result[dtype] = hazards
    return result


# ---------------------------------------------------------------------------
# Emergency contacts
# ---------------------------------------------------------------------------

_CONTACTS_BY_COUNTRY = {
    "IN": {
        "Police": "100",
        "Fire Department": "101",
        "Ambulance": "108",
        "Disaster Management Authority": "1078",
        "Women Helpline": "1091",
    },
    "JP": {
        "Police": "110",
        "Fire / Ambulance": "119",
        "Disaster Emergency": "171",
        "Coast Guard": "118",
        "NTT Disaster Board": "171",
    },
    "US": {
        "Emergency Services": "911",
        "FEMA Helpline": "1-800-621-3362",
        "Poison Control": "1-800-222-1222",
        "Red Cross": "1-800-733-2767",
        "Coast Guard": "1-800-368-5647",
    },
    "PH": {
        "Emergency Services": "911",
        "Red Cross": "143",
        "NDRRMC": "(02) 8911-5061",
        "Fire Department": "160",
        "Police": "117",
    },
    "BD": {
        "Emergency Services": "999",
        "Fire Brigade": "199",
        "Ambulance": "199",
        "Police": "999",
        "Disaster Management": "1090",
    },
    "GB": {
        "Emergency Services": "999",
        "Non-Emergency Police": "101",
        "NHS Health Line": "111",
        "Coastguard": "999",
        "Flood Line": "0345 988 1188",
    },
    "AU": {
        "Emergency Services": "000",
        "SES (Floods/Storms)": "132 500",
        "Police Assistance": "131 444",
        "Health Direct": "1800 022 222",
        "Bushfire Information": "1800 240 667",
    },
}


def _generate_emergency_contacts(country: str, short_name: str) -> dict[str, str]:
    base = _CONTACTS_BY_COUNTRY.get(country, {
        "Emergency Services": "112",
        "Police": "112",
        "Ambulance": "112",
        "Fire Department": "112",
        "Local Administration": f"{short_name} Control Room",
    })
    return dict(base)


# ---------------------------------------------------------------------------
# Supply checklist
# ---------------------------------------------------------------------------

_BASE_CHECKLIST = [
    "Drinking water (3-day supply)",
    "Non-perishable food",
    "First aid kit",
    "Prescription medicines",
    "Flashlight & batteries",
    "Power bank & charger",
    "Emergency radio",
    "Important documents (copies)",
    "Mobile phone charger",
    "Hygiene supplies",
    "Emergency contact list",
]

_EXTRA_BY_TYPE = {
    "flood": ["Waterproof bags", "Rubber boots", "Rope (15 m)"],
    "cyclone": ["Blankets", "Duct tape", "Helmet or hard hat"],
    "heatwave": ["Oral rehydration salts", "Sunscreen", "Electrolyte packets"],
}


def _generate_supply_checklist(disaster_type: str) -> list[str]:
    return _BASE_CHECKLIST + _EXTRA_BY_TYPE.get(disaster_type, [])


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

def _generate_resources(rng: random.Random) -> dict[str, int]:
    return {
        "ambulances": rng.randint(12, 36),
        "rescue_teams": rng.randint(6, 18),
        "drones": rng.randint(3, 10),
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _fake_phone(country: str, rng: random.Random) -> str:
    if country == "IN":
        return f"+91-{rng.randint(700,999)}-{rng.randint(100,999)}-{rng.randint(1000,9999)}"
    if country == "JP":
        return f"+81-{rng.randint(3,90):02d}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"
    if country == "US":
        return f"+1-{rng.randint(200,999)}-{rng.randint(200,999)}-{rng.randint(1000,9999)}"
    if country == "PH":
        return f"+63-{rng.randint(2,99):02d}-{rng.randint(100,999)}-{rng.randint(1000,9999)}"
    return f"+{rng.randint(1,99)}-{rng.randint(100,999)}-{rng.randint(100,999)}-{rng.randint(1000,9999)}"
