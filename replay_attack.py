import json
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import copy
import random

HOST = "127.0.0.1"
PORT = 8082  
PATH = "/data/aircraft.json"
TICK = 2.5  

class ReplaySpoofer:
    def __init__(self):
        self.real_aircraft = []
        self.replay_aircraft = []
        self.captured_data = {}
        self.tick_count = 0
        self.attack_phase = "capture"  # capture, replay
        
        # Simulated real aircraft
        self.real_aircraft = [
            {
                "hex": "a1b2c3",
                "flight": "REAL123",
                "gs": 450.0,
                "vr": 0.0,
                "alt_baro": 35000,
                "lat": 38.8500,
                "lon": -77.0400,
                "track": 90.0,
            }
        ]
    
    def update_real_traffic(self):
        #Simulate real aircraft movement
        for ac in self.real_aircraft:
            # Normal movement
            ac["lat"] += random.uniform(-0.001, 0.001)
            ac["lon"] += random.uniform(-0.001, 0.001)
            ac["gs"] = 450.0 + random.uniform(-10, 10)
            ac["alt_baro"] += random.choice([-25, 0, 25])
    
    def generate_replay_attacks(self):
        #Generate different types of replay attacks
        self.replay_aircraft = []
        
        if self.attack_phase == "replay" and self.captured_data:
            # Attack 1: Time-shifted replay (old data)
            if self.tick_count % 3 == 0:
                replay = copy.deepcopy(self.captured_data.get("a1b2c3", self.real_aircraft[0]))
                replay["hex"] = "time01"
                replay["flight"] = "REPLAY_TIME"
                replay["lat"] = 38.8000  # Old position
                replay["lon"] = -77.1000
                replay["gs"] = 450.0  # Old speed
                self.replay_aircraft.append(replay)
            
            # Attack 2: Location-shifted replay (wrong location)
            if self.tick_count % 4 == 0:
                replay = copy.deepcopy(self.captured_data.get("a1b2c3", self.real_aircraft[0]))
                replay["hex"] = "loc01"
                replay["flight"] = "REPLAY_LOC"
                replay["lat"] = 38.9000  # Different location
                replay["lon"] = -76.9000
                self.replay_aircraft.append(replay)
            
            # Attack 3: Ghost duplicate (same position, different ICAO)
            if self.tick_count % 5 == 0:
                replay = copy.deepcopy(self.real_aircraft[0])
                replay["hex"] = "ghost01"
                replay["flight"] = "GHOST_DUP"
                self.replay_aircraft.append(replay)
            
            # Attack 4: Stationary aircraft (possible replay)
            if self.tick_count % 6 == 0:
                replay = copy.deepcopy(self.captured_data.get("a1b2c3", self.real_aircraft[0]))
                replay["hex"] = "stat01"
                replay["flight"] = "STAT_REPLAY"
                replay["gs"] = 0.0  # Stationary
                self.replay_aircraft.append(replay)

class ReplayHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.spoofer = kwargs.pop('spoofer')
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path != PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        
        # Update simulation
        self.spoofer.tick_count += 1
        
        # Phase transition
        if self.spoofer.tick_count == 10:
            self.spoofer.attack_phase = "replay"
            print("\nREPLAY ATTACKS STARTING")
        
        # Update real traffic
        self.spoofer.update_real_traffic()
        
        # Capture real data for replay
        for ac in self.spoofer.real_aircraft:
            self.spoofer.captured_data[ac["hex"]] = copy.deepcopy(ac)
        
        # Generate replay attacks
        self.spoofer.generate_replay_attacks()
        
        # Combine real and replay aircraft - FIXED THIS LINE
        all_aircraft = self.spoofer.real_aircraft + self.spoofer.replay_aircraft
        
        # Create response
        payload = {
            "now": time.time(),
            "messages": 1000 + self.spoofer.tick_count,
            "aircraft": []
        }
        
        for ac in all_aircraft:
            payload["aircraft"].append({
                "hex": ac["hex"],
                "flight": ac["flight"],
                "gs": ac.get("gs", 0),
                "vr": ac.get("vr", 0),
                "alt_baro": ac.get("alt_baro"),
                "lat": ac.get("lat"),
                "lon": ac.get("lon"),
                "track": ac.get("track", 0),
                "seen": 0.2,
                "rssi": -20.0,
                "messages": 500
            })
        
        body = json.dumps(payload).encode("utf-8")
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, *args, **kwargs):
        # Suppress log messages
        pass

def main():
    spoofer = ReplaySpoofer()
    
    handler = lambda *args: ReplayHandler(*args, spoofer=spoofer)
    server = ThreadingHTTPServer((HOST, PORT), handler)
    
    print("REPLAY ATTACK SIMULATOR")
    print(f"http://{HOST}:{PORT}{PATH}")
    print("\nPhases:")
    print("1. First 10 ticks: Capture real aircraft")
    print("2. After tick 10: Start replay attacks")
    print("\nAttack types:")
    print("Time-shifted replays (old positions)")
    print("Location-shifted replays (wrong location)")
    print("Ghost duplicates (same position, new ICAO)")
    print("Stationary aircraft (possible replay)")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping replay simulator...")

if __name__ == "__main__":
    main()