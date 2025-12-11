import argparse
import json
import time
import random
import sys
import requests
from datetime import datetime, timezone
import math

class AttackInjector:
    def __init__(self, dump1090_url):
        self.dump1090_url = dump1090_url
        self.running = True
        
        # Attack statistics
        self.stats = {
            'real_messages': 0,
            'attack_messages': 0,
            'start_time': time.time()
        }
        
        print(f"[ATTACK INJECTOR] Connected to: {dump1090_url}")
        print("[ATTACK INJECTOR] Reading real aircraft, injecting simulated attacks")
    
    def get_real_aircraft(self):
        #Fetch real aircraft from dump1090
        try:
            response = requests.get(self.dump1090_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                aircraft = data.get('aircraft', [])
                self.stats['real_messages'] += len(aircraft)
                return aircraft
        except:
            pass
        return []
    
    def generate_flood_attack(self, real_count):
        #Generate flood attack aircraft
        attacks = []
        
        # Create many fake aircraft
        flood_count = min(50, max(10, real_count * 3))  # Scale with real traffic
        
        for i in range(flood_count):
            attack = {
                'hex': f"FLOOD{random.randint(100, 999):03d}",
                'flight': f"FL00{i:03d}",
                'lat': random.uniform(38.0, 40.0),  # Near your location
                'lon': random.uniform(-78.0, -76.0),
                'alt_baro': random.randint(5000, 35000),
                'gs': random.uniform(300, 550),
                'track': random.uniform(0, 360),
                'seen': 0.1,
                'rssi': -18.0 + random.uniform(-0.5, 0.5),
                'messages': 100,
                'attack_type': 'flood',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'simulated': True
            }
            attacks.append(attack)
        
        return attacks
    
    def generate_spoof_attack(self, real_aircraft):
        #Generate spoof/ghost aircraft based on real ones
        attacks = []
        
        if not real_aircraft:
            return attacks
        
        # Pick 1-3 real aircraft to spoof
        targets = random.sample(real_aircraft, min(3, len(real_aircraft)))
        
        for target in targets:
            # Create ghost near real aircraft
            ghost = target.copy()
            ghost['hex'] = f"GHOST{random.randint(10, 99):02d}"
            ghost['flight'] = f"GHT{random.randint(100, 999)}"
            
            # Slight position offset
            if ghost.get('lat') and ghost.get('lon'):
                ghost['lat'] += random.uniform(-0.05, 0.05)
                ghost['lon'] += random.uniform(-0.05, 0.05)
            
            # Suspicious behavior
            ghost['gs'] = ghost.get('gs', 450) * 1.3  # 30% faster
            ghost['vr'] = 0  # No vertical movement (suspicious)
            ghost['rssi'] = -21.0
            ghost['attack_type'] = 'spoof'
            ghost['timestamp'] = datetime.now(timezone.utc).isoformat()
            ghost['simulated'] = True
            
            attacks.append(ghost)
        
        return attacks
    
    def generate_replay_attack(self, real_aircraft):
        #Generate replay attacks
        attacks = []
        
        if not real_aircraft:
            return attacks
        
        for target in real_aircraft[:2]:  # First 2 aircraft
            replay = target.copy()
            replay['hex'] = f"REPLY{random.randint(10, 99):02d}"
            replay['flight'] = f"OLD{random.randint(100, 999)}"
            
            # Old timestamp (5 minutes ago)
            old_time = datetime.now(timezone.utc).timestamp() - 300
            replay['timestamp'] = datetime.fromtimestamp(old_time, tz=timezone.utc).isoformat()
            
            # Wrong location
            if replay.get('lat') and replay.get('lon'):
                replay['lat'] += random.uniform(-0.5, 0.5)
                replay['lon'] += random.uniform(-0.5, 0.5)
            
            replay['attack_type'] = 'replay'
            replay['simulated'] = True
            attacks.append(replay)
        
        return attacks
    
    def run_normal_mode(self, duration):
        #Just pass through real data
        print("[MODE] Normal mode - passing real aircraft data")
        end_time = time.time() + duration
        
        while self.running and time.time() < end_time:
            real_aircraft = self.get_real_aircraft()
            
            for ac in real_aircraft:
                # Add timestamp if missing
                if 'timestamp' not in ac:
                    ac['timestamp'] = datetime.now(timezone.utc).isoformat()
                ac['simulated'] = False
                print(json.dumps(ac))
            
            time.sleep(2.0)  # Match dump1090 update rate
    
    def run_flood_attack(self, duration):
        #Execute flood attack
        print(f"[ATTACK] Flood attack for {duration} seconds")
        end_time = time.time() + duration
        
        while self.running and time.time() < end_time:
            # Get real aircraft
            real_aircraft = self.get_real_aircraft()
            
            # Output real aircraft
            for ac in real_aircraft:
                ac['simulated'] = False
                if 'timestamp' not in ac:
                    ac['timestamp'] = datetime.now(timezone.utc).isoformat()
                print(json.dumps(ac))
            
            # Generate and output flood attacks
            flood_aircraft = self.generate_flood_attack(len(real_aircraft))
            for ac in flood_aircraft:
                self.stats['attack_messages'] += 1
                print(json.dumps(ac))
            
            # Status update
            elapsed = time.time() - end_time + duration
            if int(elapsed) % 10 == 0:  # Every 10 seconds
                print(f"[STATUS] {int(elapsed)}s: {len(real_aircraft)} real, {len(flood_aircraft)} flood")
            
            time.sleep(1.0)
    
    def run_spoof_attack(self, duration):
        #Execute spoof attack
        print(f"[ATTACK] Spoof attack for {duration} seconds")
        end_time = time.time() + duration
        
        while self.running and time.time() < end_time:
            real_aircraft = self.get_real_aircraft()
            
            # Output real aircraft
            for ac in real_aircraft:
                ac['simulated'] = False
                if 'timestamp' not in ac:
                    ac['timestamp'] = datetime.now(timezone.utc).isoformat()
                print(json.dumps(ac))
            
            # Generate and output spoof attacks
            spoof_aircraft = self.generate_spoof_attack(real_aircraft)
            for ac in spoof_aircraft:
                self.stats['attack_messages'] += 1
                print(json.dumps(ac))
            
            time.sleep(2.0)
    
    def run_replay_attack(self, duration):
        #Execute replay attack
        print(f"[ATTACK] Replay attack for {duration} seconds")
        end_time = time.time() + duration
        
        while self.running and time.time() < end_time:
            real_aircraft = self.get_real_aircraft()
            
            # Output real aircraft
            for ac in real_aircraft:
                ac['simulated'] = False
                if 'timestamp' not in ac:
                    ac['timestamp'] = datetime.now(timezone.utc).isoformat()
                print(json.dumps(ac))
            
            # Generate and output replay attacks
            replay_aircraft = self.generate_replay_attack(real_aircraft)
            for ac in replay_aircraft:
                self.stats['attack_messages'] += 1
                print(json.dumps(ac))
            
            time.sleep(2.0)
    
    def run_combined_attack(self, duration):
        #Execute all attacks in sequence
        print(f"[ATTACK] Combined attack sequence for {duration} seconds")
        
        phase_duration = duration / 4
        
        # Phase 1: Normal (baseline)
        print("\n[PHASE 1] Baseline - real aircraft only")
        self.run_normal_mode(phase_duration)
        
        # Phase 2: Flood attack
        print("\n[PHASE 2] Flood attack injection")
        self.run_flood_attack(phase_duration)
        
        # Phase 3: Spoof attack
        print("\n[PHASE 3] Spoof/Ghost attack injection")
        self.run_spoof_attack(phase_duration)
        
        # Phase 4: Replay attack
        print("\n[PHASE 4] Replay attack injection")
        self.run_replay_attack(phase_duration)
    
    def print_stats(self):
        """Print attack statistics"""
        elapsed = time.time() - self.stats['start_time']
        
        print("ATTACK INJECTION COMPLETE")
        print(f"Duration: {elapsed:.0f} seconds")
        print(f"Real aircraft messages: {self.stats['real_messages']}")
        print(f"Attack messages injected: {self.stats['attack_messages']}")
        print(f"Total messages: {self.stats['real_messages'] + self.stats['attack_messages']}")
        print(f"Attack rate: {self.stats['attack_messages'] / max(elapsed, 1):.1f} msg/sec")
        
        if self.stats['attack_messages'] > 0:
            print("\nSIMULATION SUCCESSFUL:")
def main():
    parser = argparse.ArgumentParser(
        description="ADS-B Attack Injector - No RF Transmission",
    )
    
    parser.add_argument("--dump1090", type=str, required=True,
                       help="dump1090 URL (e.g., http://localhost:8080/data/aircraft.json)")
    parser.add_argument("--attack", type=str, default="normal",
                       choices=["normal", "flood", "spoof", "replay", "all"],
                       help="Attack type to simulate")
    parser.add_argument("--duration", type=int, default=30,
                       help="Attack duration in seconds")
    parser.add_argument("--output", type=str, default="-",
                       help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    # Test connection to dump1090
    try:
        response = requests.get(args.dump1090, timeout=3)
        if response.status_code != 200:
            print(f"[ERROR] Cannot connect to dump1090 at {args.dump1090}")
            print(f"Make sure dump1090 is running:")
            print("  Terminal 1: ./dump1090 --net --write-json public_html/data --fix")
            print("  Terminal 2: cd public_html && python3 -m http.server 8080")
            return
        
        # Check if we're getting aircraft data
        data = response.json()
        aircraft_count = len(data.get('aircraft', []))
        print(f"[SUCCESS] Connected to dump1090 - {aircraft_count} aircraft detected")
        
    except Exception as e:
        print(f"[ERROR] Failed to connect to dump1090: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. Make sure dump1090 is running in Terminal 1")
        print("2. Make sure HTTP server is running in Terminal 2")
        print("3. Try: curl http://localhost:8080/data/aircraft.json")
        return
    
    # Configure output
    original_stdout = sys.stdout
    if args.output != "-":
        sys.stdout = open(args.output, 'w', buffering=1)
        print(f"[OUTPUT] Writing to file: {args.output}")
    
    # Create and run injector
    injector = AttackInjector(args.dump1090)
    
    try:
        if args.attack == "normal":
            injector.run_normal_mode(args.duration)
        elif args.attack == "flood":
            injector.run_flood_attack(args.duration)
        elif args.attack == "spoof":
            injector.run_spoof_attack(args.duration)
        elif args.attack == "replay":
            injector.run_replay_attack(args.duration)
        else:  # all
            injector.run_combined_attack(args.duration)
    
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    
    finally:
        injector.running = False
        
        # Print stats to original stdout
        if args.output != "-":
            sys.stdout.close()
            sys.stdout = original_stdout
        
        injector.print_stats()

if __name__ == "__main__":
    main()
