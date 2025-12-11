import requests
import time
from datetime import datetime

def format_value(value, unit=''):
    """Format values nicely, handling missing data"""
    if value is None or value == '':
        return '---'
    else:
        return f"{value}{unit}"

print("ADS-B Data Starting...")
print("Press Ctrl+C to stop\n")

try:
    while True:
        try:
            response = requests.get("http://localhost:8080/data/aircraft.json", timeout=5)
            data = response.json()
            all_aircraft = data.get('aircraft', [])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Total aircraft: {len(all_aircraft)}")
            print("-" * 70)
            if not all_aircraft:
                print("   No aircraft detected...")
            else:
                # Create filtered list of aircraft to display
                display_aircraft = []
                for ac in all_aircraft:
                    if ac.get('flight') or ac.get('alt_baro') or ac.get('gs'):
                        display_aircraft.append(ac)
                print(f"   Showing {len(display_aircraft)} aircraft with data")
                print()
                # Display with coordinates
                for i, ac in enumerate(display_aircraft, 1):
                    flight = ac.get('flight', '').strip() or f"ICAO:{ac.get('hex', 'UNKNOWN')}"
                    alt = format_value(ac.get('alt_baro'), 'ft')
                    speed = format_value(ac.get('gs'), 'kts')
                    # Show coordinates if available
                    if ac.get('lat') and ac.get('lon'):
                        lat = ac.get('lat')
                        lon = ac.get('lon')
                        coords = f"{lat:.4f}, {lon:.4f}"
                    else:
                        coords = "No position"
                    print(f"   {i:2}. {flight:12} | Alt: {alt:>7} | Speed: {speed:>7} | {coords}")
            time.sleep(3)
            print()
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(2)

except KeyboardInterrupt:
    print("\nData Stopped")
