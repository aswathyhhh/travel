from flask import Flask, jsonify, request
from flask import render_template
import requests

app = Flask(__name__)

GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
WIKI_URL = "https://en.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "TripAnalyzerApp/1.0 (educational project)"
}

def fetch_places(place):
    try:
        if len(place) < 3:
            return {"attractions": [], "geo": {}}

        print("Place:", place)

        # 1️⃣ Geocode
        geo_resp = requests.get(
            GEOCODE_URL,
            params={
                "q": place,
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            },
            headers=HEADERS,
            timeout=10
        )

        print("Geo status:", geo_resp.status_code)

        if geo_resp.status_code != 200:
            return {"attractions": [], "geo": {}}

        geo_data = geo_resp.json()
        print("Geo data:", geo_data)

        if not geo_data:
            return {"attractions": [], "geo": {}}

        lat = geo_data[0].get("lat")
        lon = geo_data[0].get("lon")
        address = geo_data[0].get("address", {})
        country = address.get("country")

        print("Lat/Lon:", lat, lon, "Country:", country)

        if not lat or not lon:
            return {"attractions": [], "geo": {}}

        # 2️⃣ Wikipedia geosearch
        wiki_resp = requests.get(
            WIKI_URL,
            params={
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lon}",
                "gsradius": 10000,
                "gslimit": 10,
                "format": "json"
            },
            headers=HEADERS,
            timeout=10
        )

        print("Wiki status:", wiki_resp.status_code)

        if wiki_resp.status_code != 200:
            return {"attractions": [], "geo": {"lat": lat, "lon": lon, "country": country}}

        wiki_data = wiki_resp.json()
        print("Wiki data:", wiki_data)

        geosearch = wiki_data.get("query", {}).get("geosearch", [])

        results = []
        for item in geosearch:
            results.append({
                "name": item.get("title"),
                "distance_meters": item.get("dist")
            })

        print("Final results:", results)

        return {"attractions": results, "geo": {"lat": lat, "lon": lon, "country": country}}

    except Exception as e:
        print("Server error:", e)
        return {"attractions": [], "geo": {}}

# climate helper

def get_climate_info(lat, lon, country=None):
    """Return mock climate data based on latitude (and optionally country)."""
    try:
        lat = float(lat)
    except Exception:
        return {}
    info = {}
    # simple latitude-based zones
    if abs(lat) < 23.5:
        info['climate_type'] = 'tropical'
        info['best_months'] = 'November–March'
        info['peak_season'] = False
        info['description'] = 'Warm temperatures year-round with wet/dry seasons.'
    elif abs(lat) < 66.5:
        info['climate_type'] = 'temperate'
        info['best_months'] = 'April–June, September–October'
        info['peak_season'] = True
        info['description'] = 'Mild summers and cool winters; shoulder seasons ideal.'
    else:
        info['climate_type'] = 'polar'
        info['best_months'] = 'June–August'
        info['peak_season'] = True
        info['description'] = 'Short summers; extremely cold winters.'
    # adjust for desert (example countries)
    if country and country.lower() in ['egypt','saudi arabia','uae']:
        info['climate_type'] = 'desert'
        info['best_months'] = 'November–March'
        info['peak_season'] = False
        info['description'] = 'Hot and dry; winter months are most comfortable.'
    return info


def compute_visit_plan(attractions, climate_info, geo):
    """Generate a simple crowd flow and ideal timing plan.

    The algorithm is purely illustrative: it uses the climate_info to
    decide when crowds are likely (peak vs off‑peak) and estimates sunrise
    / sunset based on latitude. Returns a small dict that the frontend can
    render in the results card.
    """
    # default times
    sunrise = "06:00"
    sunset = "18:00"

    # crude latitude-based adjustment for daylight hours
    try:
        lat = float(geo.get('lat', 0))
        offset = int((abs(lat) / 90) * 2)  # max ±2h shift
        sunrise_hour = max(0, 6 - offset)
        sunset_hour = min(23, 18 + offset)
        sunrise = f"{sunrise_hour:02d}:00"
        sunset = f"{sunset_hour:02d}:00"
    except Exception:
        pass

    peak = []
    offpeak = []
    if climate_info.get('peak_season'):
        # mid‑day crowds
        peak = ["12:00", "13:00", "14:00"]
        offpeak = ["09:00", "17:00"]
    else:
        # fewer crowds during early afternoon
        peak = ["10:00", "11:00"]
        offpeak = ["14:00", "15:00"]

    notes = "Avoid peak hours if you want fewer crowds."

    return {
        "peakTimes": peak,
        "offPeakTimes": offpeak,
        "sunrise": sunrise,
        "sunset": sunset,
        "notes": notes
    }

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/search')
def search():
    place = request.args.get('place', '').strip()
    # read optional budget and days for cost estimation ensuring default days =1
    try:
        budget = float(request.args.get('budget', 0))
        days = int(request.args.get('days', 1))
    except ValueError:
        budget = 0.0
        days = 1

    if not place:
        return jsonify({"attractions": [], "costSummary": {}, "climate": {}})

    fetched = fetch_places(place)
    attractions = fetched.get('attractions', [])
    geo = fetched.get('geo', {})

    # cost calculations using mock averages (originally USD) converted to rupees
    costSummary = {}
    if budget > 0 and days > 0:
        ticket_cost = 35.0  # average ticket/activity cost in USD
        daily_food = 30.0   # average daily food expense in USD
        rate = 82.0  # conversion rate USD→INR for costs

        # perform calculations in specified order
        food_cost = daily_food * days * rate
        activity_cost = len(attractions) * ticket_cost * rate
        total_estimated_cost = food_cost + activity_cost
        # remaining budget uses original budget value (assumed rupees)
        remaining_budget = budget - total_estimated_cost

        # debug output
        print("Budget:", budget, "days:", days)
        print("Food:", food_cost)
        print("Activities:", activity_cost)
        print("Total:", total_estimated_cost)
        print("Remaining:", remaining_budget)

        status = "Within Budget" if remaining_budget >= 0 else "Over Budget"

        costSummary = {
            "totalFood": food_cost,
            "totalActivity": activity_cost,
            "totalTrip": total_estimated_cost,
            "remainingBudget": remaining_budget,
            "budget_status": status
        }

    # climate info
    climateInfo = {}
    if geo.get('lat') and geo.get('lon'):
        climateInfo = get_climate_info(geo.get('lat'), geo.get('lon'), geo.get('country'))

    # crowd flow / visit plan
    visitPlan = compute_visit_plan(attractions, climateInfo, geo)

    return jsonify({
        "attractions": attractions,
        "costSummary": costSummary,
        "climate": climateInfo,
        "visitPlan": visitPlan
    })


@app.route('/calculate')
def calculate():
    # budget/days calculation endpoint
    try:
        budget = float(request.args.get('budget', 0))
        days = int(request.args.get('days', 0))
    except ValueError:
        return jsonify({"error":"invalid numbers"}), 400

    if days <= 0:
        return jsonify({"error":"days must be positive"}), 400

    # only calculate amount allocated for attractions/activities (20%)
    spots = (budget / days) * 0.2
    return jsonify({
        "activities": round(spots,2)
    })

if __name__ == '__main__':
    app.run(debug=True)
