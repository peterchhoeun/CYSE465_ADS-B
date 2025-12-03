import json
import sys
import time
import math
from datetime import datetime
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
        #Calculate distance in nautical miles
        if None in (lat1, lon1, lat2, lon2):
            return 9999
        
        R = 3440.065
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    def analyze(self, message):
        #Analyze a single ADS-B message
        self.message_count += 1
        
        icao = message.get('hex', 'UNKNOWN')
        flight = message.get('flight', '')
        is_simulated = message.get('simulated', False)
        
        # Initialize aircraft tracking
        if icao not in self.aircraft:
            self.aircraft[icao] = {
                'first_seen': time.time(),
                'count': 0,
                'positions': [],
                'flights': set(),
                'is_simulated': is_simulated
            }
        
        ac = self.aircraft[icao]
        ac['count'] += 1
        ac['last_seen'] = time.time()
        
        if flight:
            ac['flights'].add(flight)
        
        # Store position
        lat = message.get('lat')
        lon = message.get('lon')
        if lat is not None and lon is not None:
            ac['positions'].append((lat, lon, time.time()))
            if len(ac['positions']) > 10:
                ac['positions'].pop(0)
        
        # Run detections
        alerts = []
        
        # Detection 1: Flood signature (FLOOD in callsign)
        if 'FLOOD' in icao or 'FL00' in flight:
            alerts.append({
                'type': 'flood_attack',
                'severity': 'high',
                'message': f'Flood attack aircraft detected: {icao} ({flight})',
                'icao': icao,
                'flight': flight
            })
            self.detections['flood'] += 1
        
        # Detection 2: Spoof signature (GHOST in callsign)
        elif 'GHOST' in icao or 'GHT' in flight:
            alerts.append({
                'type': 'spoof_attack',
                'severity': 'high',
                'message': f'Spoof attack aircraft detected: {icao} ({flight})',
                'icao': icao,
                'flight': flight
            })
            self.detections['spoof'] += 1
        
        # Detection 3: Replay signature (REPLY/OLD in callsign)
        elif 'REPLY' in icao or 'OLD' in flight:
            alerts.append({
                'type': 'replay_attack',
                'severity': 'medium',
                'message': f'Replay attack aircraft detected: {icao} ({flight})',
                'icao': icao,
                'flight': flight
            })
            self.detections['replay'] += 1
        
        # Detection 4: Rate limiting
        if ac['count'] > 50:  # More than 50 messages
            alerts.append({
                'type': 'high_message_rate',
                'severity': 'medium',
                'message': f'High message rate: {icao} has {ac["count"]} messages',
                'icao': icao,
                'count': ac['count']
            })
            self.detections['other'] += 1
        
        # Detection 5: Impossible speed
        speed = message.get('gs')
        if speed and speed > 1200:  # Mach 2
            alerts.append({
                'type': 'impossible_speed',
                'severity': 'high',
                'message': f'Impossible speed: {icao} at {speed:.0f} knots',
                'icao': icao,
                'speed': speed
            })
            self.detections['other'] += 1
        
        # Detection 6: Ghost duplicates (same position)
        if lat is not None and lon is not None:
            for other_icao, other_data in self.aircraft.items():
                if other_icao == icao or not other_data['positions']:
                    continue
                
                other_lat, other_lon, other_time = other_data['positions'][-1]
                distance = self.haversine(lat, lon, other_lat, other_lon)
                
                if distance < 0.01 and abs(time.time() - other_time) < 5:
                    alerts.append({
                        'type': 'ghost_duplicate',
                        'severity': 'high',
                        'message': f'Ghost duplicate: {icao} at same position as {other_icao}',
                        'icao': icao,
                        'other_icao': other_icao,
                        'distance': distance
                    })
                    self.detections['spoof'] += 1
        
        # Add timestamp to alerts
        for alert in alerts:
            alert['time'] = datetime.now().strftime('%H:%M:%S')
            self.alerts.append(alert)
        
        return alerts
    
    def print_alert(self, alert):
        """Print alert with color coding"""
        colors = {
            'high': '\033[91m',  # Red
            'medium': '\033[93m', # Yellow
            'low': '\033[94m'     # Blue
        }
        
        color = colors.get(alert['severity'], '\033[0m')
        icon = '!!!' if alert['severity'] == 'high' else '!!' if alert['severity'] == 'medium' else '!'
        
        print(f"{color}[{icon}] {alert['time']} {alert['type'].upper()}")
        print(f"     {alert['message']}\033[0m")
    
    def print_status(self):
        """Print periodic status"""
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
        #Print final report
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
        
        # Show detected attack aircraft
        attack_aircraft = []
        for icao, data in self.aircraft.items():
            if data.get('is_simulated', False) or any(x in icao for x in ['FLOOD', 'GHOST', 'REPLY']):
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
            # Read from file
            with open(args.input, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            alerts = defense.analyze(message)
                            for alert in alerts:
                                defense.print_alert(alert)
                            
                            # Print status every 5 seconds
                            if time.time() - last_status > 5:
                                defense.print_status()
                                last_status = time.time()
                                
                        except json.JSONDecodeError:
                            pass
        else:
            # Read from stdin (piped from attack script)
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
                        
                        # Print status every 5 seconds
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