import json
import sys
import time
from datetime import datetime

class ReplayDefense:
    def __init__(self):
        self.max_age_seconds = 60 #messages older than 60 seconds are invalid
        self.alerts_triggered = 0
        print("[DEFENSE] Replay Detection Module Initialized...", file=sys.stderr)

    def analyze_message(self, message):
        icao = message.get('hex', 'UNKNOWN')
        msg_timestamp_str = message.get('timestamp')
        
        if msg_timestamp_str:
            try:
                msg_dt = datetime.fromisoformat(msg_timestamp_str.replace('Z', '+00:00'))
                msg_ts = msg_dt.timestamp()
                current_ts = time.time()
                
                age = current_ts - msg_ts
                
                if age > self.max_age_seconds:
                    self.print_alert(icao, age, is_attack=True)
                    self.alerts_triggered += 1
                else:
                    self.print_alert(icao, age, is_attack=False)
                    
            except ValueError:
                pass 

    def print_alert(self, icao, age, is_attack):
        if is_attack:
            #blue for aeplay attack
            print(f"\033[94m[!!!] REPLAY DETECTED: Aircraft {icao} timestamp is {age:.1f}s old (Threshold: 60s)\033[0m")
        else:
            #green for normal
            print(f"\033[92m[PASS] Normal Traffic: Aircraft {icao} is fresh ({age:.1f}s delay)\033[0m")

    def run(self):
        print("Reading from stdin...", file=sys.stderr)
        for line in sys.stdin:
            try:
                message = json.loads(line)
                self.analyze_message(message)
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    defense = ReplayDefense()
    try:
        defense.run()
    except KeyboardInterrupt:
        print("\n[DEFENSE] Stopping...", file=sys.stderr)
