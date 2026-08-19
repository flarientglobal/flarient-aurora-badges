#!/usr/bin/env python3
"""
Flarient Aurora Location Badges — Generator

Generates personalized SVG badges showing aurora chance for specific locations.
Each badge links to the user's corresponding Flarient forecast/location page.

Example:
  "Aurora chance tonight — Edinburgh: 42%"
  "Aurora chance tonight — Tromsø: 86%"

Badges are served as static SVG files via GitHub Pages.
Users embed them in their websites, READMEs, or social profiles.
"""

import os, sys, json, math, datetime
from pathlib import Path
import requests

FLARIENT_API = os.environ.get("FLARIENT_API_URL", "https://flarient.com").rstrip("/")
REPO_DIR = Path(os.environ.get("GITHUB_WORKSPACE", "."))
BADGES_DIR = REPO_DIR / "badges"

# Predefined locations for badge generation
LOCATIONS = [
    {"name": "Edinburgh", "lat": 55.95, "lon": -3.19, "country": "UK"},
    {"name": "Tromsø", "lat": 69.65, "lon": 18.96, "country": "Norway"},
    {"name": "Reykjavik", "lat": 64.13, "lon": -21.94, "country": "Iceland"},
    {"name": "London", "lat": 51.51, "lon": -0.13, "country": "UK"},
    {"name": "Manchester", "lat": 53.48, "lon": -2.24, "country": "UK"},
    {"name": "Glasgow", "lat": 55.86, "lon": -4.25, "country": "UK"},
    {"name": "Belfast", "lat": 54.60, "lon": -5.93, "country": "UK"},
    {"name": "Dublin", "lat": 53.35, "lon": -6.26, "country": "Ireland"},
    {"name": "Oslo", "lat": 59.91, "lon": 10.75, "country": "Norway"},
    {"name": "Stockholm", "lat": 59.33, "lon": 18.07, "country": "Sweden"},
    {"name": "Helsinki", "lat": 60.17, "lon": 24.94, "country": "Finland"},
    {"name": "Copenhagen", "lat": 55.68, "lon": 12.57, "country": "Denmark"},
    {"name": "Anchorage", "lat": 61.22, "lon": -149.90, "country": "USA"},
    {"name": "Fairbanks", "lat": 64.84, "lon": -147.72, "country": "USA"},
    {"name": "Seattle", "lat": 47.61, "lon": -122.33, "country": "USA"},
    {"name": "Minneapolis", "lat": 44.98, "lon": -93.27, "country": "USA"},
    {"name": "Toronto", "lat": 43.65, "lon": -79.38, "country": "Canada"},
    {"name": "Calgary", "lat": 51.05, "lon": -114.07, "country": "Canada"},
    {"name": "Edmonton", "lat": 53.55, "lon": -113.49, "country": "Canada"},
    {"name": "Yellowknife", "lat": 62.45, "lon": -114.37, "country": "Canada"},
    {"name": "Berlin", "lat": 52.52, "lon": 13.40, "country": "Germany"},
    {"name": "Amsterdam", "lat": 52.37, "lon": 4.90, "country": "Netherlands"},
    {"name": "Paris", "lat": 48.86, "lon": 2.35, "country": "France"},
    {"name": "New York", "lat": 40.71, "lon": -74.01, "country": "USA"},
    {"name": "Boston", "lat": 42.36, "lon": -71.06, "country": "USA"},
    {"name": "Chicago", "lat": 41.88, "lon": -87.63, "country": "USA"},
    {"name": "Dakar", "lat": 14.72, "lon": -17.47, "country": "Senegal"},
    {"name": "Cape Town", "lat": -33.92, "lon": 18.42, "country": "South Africa"},
    {"name": "Melbourne", "lat": -37.81, "lon": 144.96, "country": "Australia"},
    {"name": "Christchurch", "lat": -43.53, "lon": 172.64, "country": "New Zealand"},
    {"name": "Hobart", "lat": -42.88, "lon": 147.33, "country": "Australia"},
]


def log(msg):
    print(f"[aurora-badges] {msg}", flush=True)


# ── Calculate aurora probability ─────────────────────────────────────────
def calculate_aurora_chance(lat, kp, bz, solar_wind_speed):
    """
    Calculate aurora visibility probability for a given latitude and space weather conditions.

    Uses the relationship between magnetic latitude, Kp index, and aurora oval expansion.
    Higher Kp = aurora oval extends further south = higher probability at lower latitudes.
    """
    # Auroral oval southern boundary (latitude) based on Kp
    # Approximate formula: aurora visible at lat ≈ 65 - (Kp - 3) * 2
    if kp < 2:
        aurora_lat = 67
    elif kp >= 9:
        aurora_lat = 40
    else:
        aurora_lat = 67 - (kp - 2) * 3.5

    # Distance from aurora oval to observer
    lat_diff = abs(abs(lat) - aurora_lat)

    # Base probability from distance (closer = higher)
    if lat_diff <= 0:
        base_prob = 95
    elif lat_diff <= 2:
        base_prob = 85
    elif lat_diff <= 5:
        base_prob = 70
    elif lat_diff <= 8:
        base_prob = 50
    elif lat_diff <= 12:
        base_prob = 30
    elif lat_diff <= 15:
        base_prob = 15
    elif lat_diff <= 20:
        base_prob = 5
    else:
        base_prob = 0

    # Adjust for Bz (southward = better for aurora)
    if bz is not None and bz < -5:
        base_prob = min(95, base_prob + 10)
    elif bz is not None and bz < -10:
        base_prob = min(95, base_prob + 15)

    # Adjust for solar wind speed
    if solar_wind_speed is not None and solar_wind_speed > 500:
        base_prob = min(95, base_prob + 5)
    elif solar_wind_speed is not None and solar_wind_speed > 700:
        base_prob = min(95, base_prob + 10)

    return max(0, min(95, int(base_prob)))


# ── Fetch current space weather ───────────────────────────────────────────
def fetch_space_weather():
    """Fetch current Kp, Bz, and solar wind speed from NOAA."""
    kp, bz, speed = 2.0, 0, 400  # defaults
    try:
        kp_resp = requests.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=15)
        kp_data = kp_resp.json()
        if kp_data:
            kp = float(kp_data[-1].get("kp", 2))
    except Exception as e:
        log(f"  Kp fetch failed: {e}")

    try:
        sw_resp = requests.get("https://services.swpc.noaa.gov/products/ace/ace_swepam_1m.json", timeout=15)
        sw_data = sw_resp.json()
        if sw_data and len(sw_data) > 1:
            latest = sw_data[-1]
            bz = float(latest[2]) if len(latest) > 2 else 0
            speed = float(latest[3]) if len(latest) > 3 else 400
    except Exception as e:
        log(f"  Solar wind fetch failed: {e}")

    return kp, bz, speed


# ── Generate SVG badge ────────────────────────────────────────────────────
def generate_svg(location, chance, kp):
    """Generate an SVG badge showing aurora chance for a location."""
    name = location["name"]
    lat = location["lat"]

    # Color based on chance
    if chance >= 70:
        color = "#22c55e"  # green
        label = "High"
    elif chance >= 40:
        color = "#f59e0b"  # amber
        label = "Moderate"
    elif chance >= 15:
        color = "#6366f1"  # indigo
        label = "Low"
    else:
        color = "#64748b"  # slate
        label = "Minimal"

    # Badge dimensions
    width = 320
    height = 80

    # Create slug for URL
    slug = name.lower().replace(" ", "-").replace("ø", "o").replace("å", "a")
    flarient_url = f"{FLARIENT_API}/aurora-forecast?location={slug}"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0a0620"/>
      <stop offset="100%" stop-color="#1a0a3e"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="12" fill="url(#bg)" stroke="{color}" stroke-width="1.5"/>
  <circle cx="30" cy="40" r="16" fill="none" stroke="{color}" stroke-width="2"/>
  <circle cx="30" cy="40" r="8" fill="{color}" opacity="0.3"/>
  <text x="58" y="28" font-family="system-ui, sans-serif" font-size="11" fill="#94a3b8" font-weight="500">AURORA CHANCE TONIGHT</text>
  <text x="58" y="48" font-family="system-ui, sans-serif" font-size="16" fill="#e8eaf2" font-weight="700">{name}</text>
  <text x="58" y="66" font-family="system-ui, sans-serif" font-size="10" fill="{color}" font-weight="600">{label} · Kp {kp}</text>
  <text x="{width - 18}" y="48" font-family="system-ui, sans-serif" font-size="22" fill="{color}" font-weight="800" text-anchor="end">{chance}%</text>
  <text x="{width - 18}" y="66" font-family="system-ui, sans-serif" font-size="8" fill="#64748b" text-anchor="end">flarient.com</text>
</svg>'''
    return svg, slug


# ── Generate index page ──────────────────────────────────────────────────
def generate_index(badges_data):
    """Generate an HTML index page listing all available badges."""
    log("Generating index page...")

    badge_cards = ""
    for b in badges_data:
        badge_cards += f'''
    <div class="badge-card">
      <img src="badges/{b['slug']}.svg" alt="Aurora chance {b['name']}" width="320" height="80"/>
      <div class="badge-info">
        <h3>{b['name']}</h3>
        <p>Aurora chance: <strong>{b['chance']}%</strong> · Kp {b['kp']}</p>
        <code>&lt;img src="https://flarientglobal.github.io/flarient-aurora-badges/badges/{b['slug']}.svg" alt="Aurora chance {b['name']}"&gt;</code>
      </div>
    </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flarient Aurora Location Badges</title>
  <meta name="description" content="Personalized aurora chance badges for cities worldwide. Embed them on your website or profile.">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; background: #05030f; color: #e8eaf2; min-height: 100vh; padding: 2rem; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    h1 {{ font-size: 1.75rem; margin-bottom: 0.5rem; }}
    .subtitle {{ color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }}
    .badge-card {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; }}
    .badge-info h3 {{ font-size: 1.1rem; margin-bottom: 0.25rem; }}
    .badge-info p {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.5rem; }}
    .badge-info code {{ font-size: 0.75rem; color: #6366f1; background: rgba(99,102,241,0.1); padding: 0.25rem 0.5rem; border-radius: 4px; word-break: break-all; }}
    .footer {{ margin-top: 3rem; padding-top: 2rem; border-top: 1px solid rgba(255,255,255,0.1); color: #64748b; font-size: 0.85rem; }}
    .footer a {{ color: #6366f1; text-decoration: none; }}
    @media (max-width: 640px) {{ .badge-card {{ flex-direction: column; align-items: flex-start; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Flarient Aurora Location Badges</h1>
    <p class="subtitle">Personalized aurora chance badges for cities worldwide. Updated hourly with live NOAA data. Embed them anywhere.</p>
    {badge_cards}
    <div class="footer">
      <p>Powered by <a href="https://flarient.com">Flarient</a> — the space weather intelligence platform.</p>
      <p>Data: NOAA SWPC · Updated: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</p>
    </div>
  </div>
</body>
</html>'''

    (REPO_DIR / "index.html").write_text(html, encoding="utf-8")
    log("  Index page generated")


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    log("=== Flarient Aurora Location Badges ===")
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    kp, bz, speed = fetch_space_weather()
    log(f"  Current conditions: Kp={kp}, Bz={bz}, Speed={speed}km/s")

    badges_data = []
    for loc in LOCATIONS:
        chance = calculate_aurora_chance(loc["lat"], kp, bz, speed)
        svg, slug = generate_svg(loc, chance, kp)
        (BADGES_DIR / f"{slug}.svg").write_text(svg, encoding="utf-8")
        badges_data.append({"name": loc["name"], "slug": slug, "chance": chance, "kp": kp})
        log(f"  {loc['name']}: {chance}%")

    generate_index(badges_data)
    log(f"Generated {len(badges_data)} badges")
    log("Done")


if __name__ == "__main__":
    main()
