import requests
import time
import json
from datetime import datetime
from collections import defaultdict

#this first DATA_URL is used for when testing with the spoofer
DATA_URL = "http://127.0.0.1:8081/data/aircraft.json"

#this second one is used for when we want to actually use it with real planes like with our dump1090 demo lab
#DATA_URL = "http://localhost:8080/data/aircraft.json"

POLL_SEC = 2.5

# Baseline learning
MIN_SAMPLES = 5       # samples before judging
EWMA_ALPHA  = 0.25    # how fast baseline adapts (0..1)

FLAGS_OUTFILE = "flags.json"

def now_str():
    return datetime.utcnow().isoformat() + "Z"

def pct_diff(curr, base):
    """Absolute percent difference |curr - base| / base; None if base invalid/zero."""
    try:
        base = float(base)
        curr = float(curr)
        if base == 0:
            return None
        return abs(curr - base) / abs(base)
    except Exception:
        return None

def phase_for(alt, vr_mag):
    """
    Very simple phase classifier from altitude (ft) and |vertical rate| (fpm).
    Returns a string phase.
    """
    if alt is None:
        # Without altitude, default to conservative 'climb/descent' to avoid over-flagging
        return "climb_descent"

    if alt < 1500 or (alt < 3000 and (vr_mag or 0) > 1000):
        return "ground_takeoff"
    if alt < 5000:
        return "approach"
    if alt < 10000 or (vr_mag or 0) >= 500:
        return "climb_descent"
    # cruise if high and relatively steady
    return "cruise"

def thresholds_for(phase):
    """
    Returns (SUSP_PCT, SPOOF_PCT) for the detected phase.
    Values are fractions (e.g., 0.10 = 10%).
    """
    if phase == "cruise":
        return 0.05, 0.10
    if phase == "climb_descent":
        return 0.10, 0.20
    if phase == "approach":
        return 0.12, 0.25
    if phase == "ground_takeoff":
        return 0.15, 0.30
    # fallback
    return 0.10, 0.20

# Per-aircraft baselines and counts
# state[hex] = {"gs_mean":..., "vr_mean":..., "alt_mean":..., "n": int}
state = defaultdict(lambda: {"gs_mean": None, "vr_mean": None, "alt_mean": None, "n": 0})
flags = []

def save_flags():
    try:
        with open(FLAGS_OUTFILE, "w") as f:
            json.dump({"last_updated": now_str(), "flags": flags}, f, indent=2)
    except Exception as e:
        print(f"ERROR writing flags file: {e}")

print("ADS-B Percent-Diff Validator (phase-aware) starting...")
print("Press Ctrl+C to stop\n")

try:
    while True:
        try:
            r = requests.get(DATA_URL, timeout=5)
            payload = r.json()
            aircraft = payload.get("aircraft", []) or []
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Total aircraft: {len(aircraft)}")

            for ac in aircraft:
                hex_id = ac.get("hex")
                if not hex_id:
                    continue

                gs   = ac.get("gs")         # knots
                vr   = ac.get("vr")         # fpm (can be +/-)
                alt  = ac.get("alt_baro")   # feet
                vr_mag = abs(vr) if vr is not None else None

                st = state[hex_id]
                n  = st["n"]

                # Determine phase, then phase-based thresholds
                phase = phase_for(alt, vr_mag)
                SUSP_PCT, SPOOF_PCT = thresholds_for(phase)

                # Percent deviations vs baseline (if baseline exists)
                gs_dev  = pct_diff(gs,     st["gs_mean"])   if st["gs_mean"]   is not None and gs     is not None else None
                vr_dev  = pct_diff(vr_mag, st["vr_mean"])   if st["vr_mean"]   is not None and vr_mag is not None else None
                alt_dev = pct_diff(alt,    st["alt_mean"])  if st["alt_mean"]  is not None and alt    is not None else None

                deviations = []
                if gs_dev  is not None:  deviations.append(("gs",  gs_dev))
                if vr_dev  is not None:  deviations.append(("vr",  vr_dev))
                if alt_dev is not None:  deviations.append(("alt", alt_dev))

                # Decide status only if we have enough history
                if n >= MIN_SAMPLES and deviations:
                    over_spoof = [m for m, d in deviations if d >= SPOOF_PCT]
                    over_susp  = [m for m, d in deviations if d >= SUSP_PCT]

                    if len(over_spoof) >= 2:
                        entry = {
                            "hex": hex_id,
                            "flight": (ac.get("flight") or "").strip() or None,
                            "deviations": {m: round(d, 4) for m, d in deviations},
                            "phase": phase,
                            "status": "spoofed",
                            "criteria": f">= {int(SPOOF_PCT*100)}% on >= 2 metrics (phase={phase})",
                            "timestamp": now_str()
                        }
                        flags.append(entry)
                        print(f"!!! SPOOFED {hex_id} | {phase} | dev: {entry['deviations']}  (>= {int(SPOOF_PCT*100)}% on >=2)")
                        save_flags()
                    elif len(over_susp) >= 1:
                        entry = {
                            "hex": hex_id,
                            "flight": (ac.get("flight") or "").strip() or None,
                            "deviations": {m: round(d, 4) for m, d in deviations},
                            "phase": phase,
                            "status": "suspicious",
                            "criteria": f">= {int(SUSP_PCT*100)}% on any metric (phase={phase})",
                            "timestamp": now_str()
                        }
                        flags.append(entry)
                        print(f"** Suspicious {hex_id} | {phase} | dev: {entry['deviations']}  (>= {int(SUSP_PCT*100)}% on any)")
                        save_flags()

                # Update EWMA baselines (learn every tick)
                if gs is not None:
                    st["gs_mean"] = float(gs) if st["gs_mean"] is None else (1 - EWMA_ALPHA) * st["gs_mean"] + EWMA_ALPHA * float(gs)
                if vr_mag is not None:
                    st["vr_mean"] = float(vr_mag) if st["vr_mean"] is None else (1 - EWMA_ALPHA) * st["vr_mean"] + EWMA_ALPHA * float(vr_mag)
                if alt is not None:
                    st["alt_mean"] = float(alt) if st["alt_mean"] is None else (1 - EWMA_ALPHA) * st["alt_mean"] + EWMA_ALPHA * float(alt)

                if gs is not None or vr_mag is not None or alt is not None:
                    st["n"] = n + 1

        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(POLL_SEC)

except KeyboardInterrupt:
    print("\nStopped.")
    save_flags()
