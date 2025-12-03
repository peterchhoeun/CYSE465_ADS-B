import requests
import time
import json
from datetime import datetime, timezone
from collections import defaultdict
import math

DATA_SOURCE = "http://127.0.0.1:8082/data/aircraft.json"
POLL_INTERVAL = 2.5

class FinalDetector:
    def __init__(self):
        self.aircraft_history = defaultdict(lambda: {
            'positions': [],
            'timestamps': [],
            'type': 'unknown',  # 'legitimate' or 'replay'
            'first_seen': None
        })
        self.detections = []
        self.scan_count = 0
        
    def haversine(self, lat1, lon1, lat2, lon2):
        #Calculate distance in nautical miles
        if None in (lat1, lon1, lat2, lon2):
            return 9999
        
        R = 3440.065
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    def analyze_aircraft(self, aircraft):
        #Analyze a single aircraft and return analysis results
        icao = aircraft.get('hex', 'UNKNOWN')
        flight = aircraft.get('flight', '').strip() or f"ICAO:{icao}"
        lat = aircraft.get('lat')
        lon = aircraft.get('lon')
        speed = aircraft.get('gs', 0)
        
        analysis = {
            'icao': icao,
            'flight': flight,
            'status': 'legitimate',
            'violations': [],
            'confidence': 0
        }
        
        if not icao or lat is None or lon is None:
            analysis['status'] = 'invalid_data'
            return analysis
        
        # Check 1: Replay signature in flight name
        replay_keywords = ['REPLAY', 'GHOST', 'STAT_', 'OLD_', 'MOVED_']
        if any(keyword in flight for keyword in replay_keywords):
            analysis['status'] = 'replay'
            analysis['violations'].append(f"Replay signature in callsign")
            analysis['confidence'] = 90
        
        # Get or create history
        history = self.aircraft_history[icao]
        current_time = time.time()
        
        if history['first_seen'] is None:
            history['first_seen'] = current_time
            # Set type based on initial analysis
            history['type'] = 'replay' if analysis['status'] == 'replay' else 'legitimate'
        
        # Store position
        history['positions'].append((lat, lon, current_time))
        if len(history['positions']) > 15:
            history['positions'].pop(0)
        
        # For legitimate aircraft, run additional checks
        if history['type'] == 'legitimate' and len(history['positions']) >= 3:
            # Check for duplicate position (ghost attack)
            for other_icao, other_history in self.aircraft_history.items():
                if other_icao == icao or not other_history['positions']:
                    continue
                
                other_lat, other_lon, other_time = other_history['positions'][-1]
                distance = self.haversine(lat, lon, other_lat, other_lon)
                time_diff = abs(current_time - other_time)
                
                # Same position, different ICAO, recent time
                if distance < 0.01 and time_diff < 5:
                    analysis['status'] = 'replay'
                    analysis['violations'].append(f"Ghost duplicate of {other_icao}")
                    analysis['confidence'] = 85
                    history['type'] = 'replay'
                    break
        
        return analysis
    
    def run_demo(self):
        print(f"\nData source: {DATA_SOURCE}")
        print(f"Scan interval: {POLL_INTERVAL} seconds")
        print("\nDetection Methods:")
        print("1. Callsign signature analysis")
        print("2. Ghost duplicate detection")
        print("3. Position history validation")
        print("Starting detection system...")
        
        try:
            while True:
                self.scan_count += 1
                current_time = datetime.now()
                
                try:
                    # Fetch aircraft data
                    response = requests.get(DATA_SOURCE, timeout=5)
                    data = response.json()
                    aircraft_list = data.get("aircraft", [])
                    
                    print(f"\n[{current_time.strftime('%H:%M:%S')}] Scan #{self.scan_count}")
                    print(f"Processing {len(aircraft_list)} aircraft")
                    
                    # Track counts
                    legitimate_count = 0
                    replay_count = 0
                    new_detections = []
                    
                    # Analyze each aircraft
                    for aircraft in aircraft_list:
                        analysis = self.analyze_aircraft(aircraft)
                        
                        # Display analysis
                        status_icon = "(real)" if analysis['status'] == 'legitimate' else "(alert)"
                        print(f"{status_icon} {analysis['flight']} ({analysis['icao'][:6]})")
                        
                        if analysis['status'] == 'replay' and analysis['violations']:
                            replay_count += 1
                            for violation in analysis['violations']:
                                print(f"{violation}")
                            
                            # Record new detection
                            if not any(d['icao'] == analysis['icao'] 
                                     for d in self.detections[-5:]):  # Avoid duplicates
                                detection_record = {
                                    'timestamp': current_time.isoformat(),
                                    'scan': self.scan_count,
                                    'icao': analysis['icao'],
                                    'flight': analysis['flight'],
                                    'violations': analysis['violations'],
                                    'confidence': analysis['confidence']
                                }
                                new_detections.append(detection_record)
                                self.detections.append(detection_record)
                        else:
                            legitimate_count += 1
                    
                    # Summary for this scan
                    if replay_count > 0:
                        print(f"DETECTED: {replay_count} replay attack(s)")
                        for detection in new_detections:
                            print(f"{detection['flight']}: {', '.join(detection['violations'])}")
                    else:
                        print(f"CLEAR: {legitimate_count} legitimate aircraft")
                    
                    # Save results periodically
                    if self.scan_count % 10 == 0:
                        self.save_results()
                    
                    time.sleep(POLL_INTERVAL)
                    
                except requests.exceptions.ConnectionError:
                    print(f"Connection failed")
                    print(f"  Expected: {DATA_SOURCE}")
                    time.sleep(10)
                except Exception as e:
                    print(f"Error: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            self.shutdown()
    
    def save_results(self):
        #Save detection results
        try:
            with open("detection_results.json", "w") as f:
                json.dump({
                    'total_scans': self.scan_count,
                    'total_detections': len(self.detections),
                    'aircraft_tracked': len(self.aircraft_history),
                    'detections': self.detections[-20:],  # Last 20 detections
                    'summary': {
                        'legitimate_aircraft': sum(1 for h in self.aircraft_history.values() 
                                                 if h['type'] == 'legitimate'),
                        'replay_aircraft': sum(1 for h in self.aircraft_history.values() 
                                              if h['type'] == 'replay'),
                        'detection_rate': len(self.detections) / max(self.scan_count, 1)
                    }
                }, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save results: {e}")
    
    def shutdown(self):
        #Display shutdown summary
        print("\nSystem Shutdown")

        legitimate = sum(1 for h in self.aircraft_history.values() 
                        if h['type'] == 'legitimate')
        replay = sum(1 for h in self.aircraft_history.values() 
                    if h['type'] == 'replay')
        
        print(f"Total scans: {self.scan_count}")
        print(f"Aircraft tracked: {len(self.aircraft_history)}")
        print(f"Legitimate: {legitimate}")
        print(f"Replay attacks: {replay}")
        print(f"Total detections: {len(self.detections)}")
        
        if self.detections:
            print("Attack Timeline:")
            for i, detection in enumerate(self.detections[-10:], 1):  # Last 10
                print(f"  {i}. Scan {detection['scan']}: {detection['flight']}")
                for violation in detection['violations'][:2]:  # First 2 violations
                    print(f"       {violation}")
        
        self.save_results()
        print(f"\nComplete results saved to: detection_results.json")

def main():
    print("\nPRE-FLIGHT CHECK")
    print("Before starting, ensure:")
    print("1. replay_attack.py is running (provides data on port 8082)")
    print("2. You can connect with: curl http://127.0.0.1:8082/data/aircraft.json")
    
    detector = FinalDetector()
    detector.run_demo()

if __name__ == "__main__":
    main()