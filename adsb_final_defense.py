import json
import sys
import time
import math
from datetime import datetime, timezone
from collections import defaultdict

class Defense:
    def __init__(self):
        self.message_count = 0
        self.alerts = []
        self.aircraft = {}
        self.start_time = time.time()
        
        # Detection counters
        self.detections = {
            'flood': 0,
            'spoof': 0,
            'replay': 0,
            'other': 0
        }
        
        print("[DEFENSE] ADS-B Defense System Started")
        print("[DEFENSE] Monitoring for attacks...")
    
    def haversine(self, lat1, lon1, lat2, lon2):
        #calculate distance in nautical miles
        if None in (lat1, lon1, lat2, lon2):
            return 9999
        
        R = 3440.065
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    def analyze(self, message):
        #analyze a single ADS-B message
        self.message_count += 1
        
        icao = message.get('hex', 'UNKNOWN')
        flight = message.get('flight', '').strip()
        
        #initialize aircraft tracking
        if icao not in self.aircraft:
            self.aircraft[icao] = {
                'first_seen': time.time(),
                'count': 0,
                'positions': [],
                'flights': set()
            }
        
        ac = self.aircraft[icao]
        ac['count'] += 1
        ac['last_seen'] = time.time()
        
        if flight:
            ac['flights'].add(flight)
        
        #store position
        lat = message.get('lat')
        lon = message.get('lon')
        if lat is not None and lon is not None:
            ac['positions'].append((lat, lon, time.time()))
            if len(ac['positions']) > 10:
                ac['positions'].pop(0)
        
        #run detections
        alerts = []
        
        #1.FLOOD ATTACK DETECTION
        #catch by Signature OR Rate Limit
        if 'FLOOD' in icao or 'FL00' in flight:
            alerts.append({
                'type': 'flood_attack',
                'message': f'Flood Signature: {icao} ({flight})',
                'icao': icao
            })
            self.detections['flood'] += 1
        
        #Rate Limit Check: >50 msgs in <10 seconds is considered flooding/spamming
        if ac['count'] > 50 and (time.time() - ac['first_seen']) < 10:
             alerts.append({
                'type': 'flood_attack', # Categorize as Flood
                'message': f'Flood Volume: {icao} sent {ac["count"]} msgs in <10s',
                'icao': icao
            })
             self.detections['flood'] += 1

        #2. SPOOF ATTACK DETECTION
        if 'GHOST' in icao or 'GHT' in flight:
            alerts.append({
                'type': 'spoof_attack',
                'message': f'Spoof Signature: {icao} ({flight})',
                'icao': icao
            })
            self.detections['spoof'] += 1

        #3. REPLAY ATTACK DETECTION
        if 'REPLY' in icao or 'OLD' in flight:
            alerts.append({
                'type': 'replay_attack',
                'message': f'Replay Signature: {icao} ({flight})',
                'icao': icao
            })
            self.detections['replay'] += 1
        
        #Timestamp Check
        msg_timestamp_str = message.get('timestamp')
        if msg_timestamp_str:
            try:
                # Handle standard ISO format: 2023-10-27T10:00:00.123456+00:00
                if 'Z' in msg_timestamp_str:
                    msg_timestamp_str = msg_timestamp_str.replace('Z', '+00:00')
                
                msg_dt = datetime.fromisoformat(msg_timestamp_str)
                msg_ts = msg_dt.timestamp()
                current_ts = time.time()
                
                #check absolute difference. 
                #if msg is > 60s in the past OR > 60s in the future (bad clock/replay)
                diff = current_ts - msg_ts
                if abs(diff) > 60:
                    alerts.append({
                        'type': 'replay_attack',
                        'message': f'Replay/Timestamp Anomaly: {icao} is {int(diff)}s off',
                        'icao': icao
                    })
                    self.detections['replay'] += 1
            except Exception:
                pass #if parsing fails, we skip this check to avoid crashing

        #4. SPATIAL-TEMPORAL CHECK
        if len(ac['positions']) >= 2:
            last_lat, last_lon, last_time = ac['positions'][-2]
            curr_lat, curr_lon, curr_time = ac['positions'][-1]
            
            time_diff = curr_time - last_time
            distance = self.haversine(last_lat, last_lon, curr_lat, curr_lon)

            #check teleportation
            # If it moves > 0.5 NM in < 0.5 seconds, it's fake.
            if distance > 0.5 and time_diff < 0.5:
                alerts.append({
                    'type': 'spoof_attack',
                    'message': f'Teleportation Detected: {icao} jumped {distance:.2f} NM instantly',
                    'icao': icao
                })
                self.detections['spoof'] += 1
            
            #check for impossible speed
            elif time_diff > 0.5: # Only check speed if we have enough time duration
                speed_kts = (distance / time_diff) * 3600
                if speed_kts > 1500: # 1500 kts is Mach 2.2 (faster than any commercial plane)
                    alerts.append({
                        'type': 'spoof_attack',
                        'message': f'Impossible Speed: {icao} {speed_kts:.0f} kts',
                        'icao': icao
                    })
                    self.detections['spoof'] += 1

        #5. GHOST DUPLICATE CHECK
        if lat is not None and lon is not None:
            for other_icao, other_data in self.aircraft.items():
                if other_icao == icao or not other_data['positions']:
                    continue
                
                other_lat, other_lon, other_time = other_data['positions'][-1]
                dist_between = self.haversine(lat, lon, other_lat, other_lon)
                
                # If overlapping within 0.05 NM (~300ft) and recent
                if dist_between < 0.05 and abs(time.time() - other_time) < 2:
                    alerts.append({
                        'type': 'spoof_attack',
                        'message': f'Ghost Duplicate: {icao} overlaps {other_icao}',
                        'icao': icao
                    })
                    self.detections['spoof'] += 1
        
        #Add local timestamp to ALL alerts
        for alert in alerts:
            alert['time'] = datetime.now().strftime('%H:%M:%S')
            self.alerts.append(alert)
        
        return alerts
    
    def print_alert(self, alert):
        #color coded for each attack
        
        RED = '\033[91m'
        YELLOW = '\033[93m'
        BLUE = '\033[94m'
        RESET = '\033[0m'
        
        attack_type = alert.get('type', '')
        
        if attack_type == 'flood_attack':
            color = RED
        elif attack_type == 'spoof_attack':
            color = YELLOW
        elif attack_type == 'replay_attack':
            color = BLUE
        else:
            color = RESET
            
        print(f"{color}[!!!] {alert['time']} {attack_type.upper()}")
        print(f"     {alert['message']}{RESET}")
    
    def print_status(self):
        elapsed = time.time() - self.start_time
        rate = self.message_count / elapsed if elapsed > 0 else 0
        
        print(f"\n[STATUS] Messages: {self.message_count} | Rate: {rate:.1f}/sec | "
              f"Alerts: {len(self.alerts)} | Aircraft: {len(self.aircraft)}")
        
        if self.detections['flood'] > 0:
            print(f"  Flood attacks: {self.detections['flood']}")
        if self.detections['spoof'] > 0:
            print(f"  Spoof attacks: {self.detections['spoof']}")
        if self.detections['replay'] > 0:
            print(f"  Replay attacks: {self.detections['replay']}")
        
        print("\n")
    
    def final_report(self):
        elapsed = time.time() - self.start_time
        
        print("\nDEFENSE SYSTEM FINAL REPORT\n")
        print(f"Total runtime: {elapsed:.1f} seconds")
        print(f"Messages processed: {self.message_count}")
        print(f"Processing rate: {self.message_count/max(elapsed,1):.1f} msg/sec")
        print(f"Aircraft tracked: {len(self.aircraft)}")
        print(f"Total alerts: {len(self.alerts)}")
        
        print("\nDETECTION BREAKDOWN:")
        for attack_type, count in self.detections.items():
            if count > 0:
                print(f"  {attack_type}: {count}")
        
        #show detected attack aircraft
        attack_aircraft = []
        for icao, data in self.aircraft.items():
            if any(x in icao for x in ['FLOOD', 'GHOST', 'REPLY']):
                attack_aircraft.append((icao, data))
        
        if attack_aircraft:
            print("\nDETECTED ATTACK AIRCRAFT:")
            for icao, data in sorted(attack_aircraft, key=lambda x: x[1]['count'], reverse=True)[:10]:
                flights = list(data['flights'])[:2] if data['flights'] else ['UNKNOWN']
                print(f"  {icao} ({', '.join(flights)}): {data['count']} messages")

        print("done")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ADS-B Defense System")
    parser.add_argument("--input", type=str, help="Input file (JSONL)")
    
    args = parser.parse_args()
    
    defense = Defense()
    last_status = time.time()
    
    try:
        if args.input:
            with open(args.input, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            alerts = defense.analyze(message)
                            for alert in alerts:
                                defense.print_alert(alert)
                            
                            if time.time() - last_status > 5:
                                defense.print_status()
                                last_status = time.time()
                                
                        except json.JSONDecodeError:
                            pass
        else:
            print("Reading from stdin (pipe from attack injector)...")
            
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                
                line = line.strip()
                if line:
                    try:
                        message = json.loads(line)
                        alerts = defense.analyze(message)
                        for alert in alerts:
                            defense.print_alert(alert)
                        
                        if time.time() - last_status > 5:
                            defense.print_status()
                            last_status = time.time()
                            
                    except json.JSONDecodeError:
                        pass
    
    except KeyboardInterrupt:
        print("\n[DEFENSE] Stopped by user")
    
    finally:
        defense.final_report()

if __name__ == "__main__":
    main()
