import json
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HOST = "127.0.0.1"
PORT = 8081
PATH = "/data/aircraft.json"
TICK = 2.0  # seconds between updates

state = {
    "legit": {
        "hex": "a1b2c3",
        "flight": "LEGIT123",
        "gs": 450.0,
        "vr": 0.0,
        "alt_baro": 35000,
        "lat": 38.8500,
        "lon": -77.0400,
    },
    "ghost": {
        "hex": "deaf01",
        "flight": "GHOST01",
        "gs": 440.0,
        "vr": 0.0,
        "alt_baro": 34000,
        "lat": 38.9500,
        "lon": -77.1400,
    }
}

lock = threading.Lock()
tick_count = 0

def step_sim():
    global tick_count
    while True:
        time.sleep(TICK)
        tick_count += 1
        with lock:
            st = state["legit"]
            st["gs"] = 450.0 + 0.02 * ((tick_count % 20) - 10)
            st["vr"] = 0.0
            st["alt_baro"] = 35000 + (1 if (tick_count % 2 == 0) else -1)
            st["lat"] += 0.0001
            st["lon"] += 0.0001

            gh = state["ghost"]
            if tick_count <= 10:
                gh["gs"] = 440.0 + 0.05 * ((tick_count % 10) - 5)
                gh["vr"] = 0.0
                gh["alt_baro"] = 34000 + (1 if (tick_count % 2 == 0) else -1)
            else:
                gh["gs"] = 440.0 * 1.35
                gh["alt_baro"] = int(34000 * 0.70)
                gh["vr"] = 1200.0 if (tick_count % 2 == 0) else 800.0
                gh["lat"] += 0.0002
                gh["lon"] += 0.0002

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        with lock:
            aircraft = []
            for key in ("legit", "ghost"):
                ac = state[key]
                aircraft.append({
                    "hex": ac["hex"],
                    "flight": ac["flight"],
                    "gs": ac["gs"],
                    "vr": ac["vr"],
                    "alt_baro": ac["alt_baro"],
                    "lat": ac["lat"],
                    "lon": ac["lon"],
                    "seen": 0.2,
                    "rssi": -20.0 if key == "legit" else -21.0,
                    "messages": 1000 + tick_count
                })
            payload = {
                "now": time.time(),
                "aircraft": aircraft
            }
            body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        return

def main():
    t = threading.Thread(target=step_sim, daemon=True)
    t.start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving simulated aircraft at http://{HOST}:{PORT}{PATH}")
    print("First ~10 ticks are normal; spoof deviations start after that.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping simulator...")

if __name__ == "__main__":
    main()
