import argparse
import json
import time
import sys
from datetime import datetime, timezone

class ReplayAttackInjector:
    def __init__(self):
        self.running = True

    def generate_message(self, is_replay=False):
        current_time = time.time()
        
        #If its a replay, we inject an old timestamp (5 minutes ago)
        #If its real, we use the current time
        msg_time = current_time - 300 if is_replay else current_time
        
        message = {
            "hex": "A83781" if is_replay else "REAL01",
            "flight": "UA1234" if is_replay else "REAL123",
            "lat": 38.9072,
            "lon": -77.0369,
            "alt_baro": 12000,
            "gs": 450,
            "timestamp": datetime.fromtimestamp(msg_time, tz=timezone.utc).isoformat(),
            "simulated": True,
            "type": "REPLAY_ATTACK" if is_replay else "NORMAL"
        }
        return message

    def run(self, duration):
        print(f"[ATTACKER] Starting Replay Attack Simulation for {duration} seconds...", file=sys.stderr)
        end_time = time.time() + duration
        
        while time.time() < end_time:
            #1. Send a "Live" message
            live_msg = self.generate_message(is_replay=False)
            print(json.dumps(live_msg))
            sys.stdout.flush()
            
            #2. Send a "Replay" message
            replay_msg = self.generate_message(is_replay=True)
            print(json.dumps(replay_msg))
            sys.stdout.flush()
            
            time.sleep(1.0) # Send data every second

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay Attack")
    parser.add_argument("--duration", type=int, default=10, help="Duration (seconds)")
    args = parser.parse_args()

    injector = ReplayAttackInjector()
    try:
        injector.run(args.duration)
    except KeyboardInterrupt:
        pass
