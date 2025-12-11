#!/usr/bin/env python3
"""
flood_attack.py

Simulates an ADS-B flooding attack by generating ADS-B-like
JSON messages at a high rate.
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone

def random_icao():
    return "".join(random.choices("0123456789ABCDEF", k=6))

def random_position():
    lat = random.uniform(35.0, 45.0)
    lon = random.uniform(-85.0, -75.0)
    alt = random.randint(1000, 40000)
    return lat, lon, alt

def generate_message(icao=None, rssi_base=-20.0):
    if icao is None:
        icao = random_icao()
    lat, lon, alt = random_position()
    rssi = rssi_base + random.uniform(-2.0, 2.0)
    now = datetime.now(timezone.utc).isoformat()
    msg = {
        "icao": icao,
        "lat": lat,
        "lon": lon,
        "altitude": alt,
        "rssi": rssi,
        "timestamp": now
    }
    return msg

def main():
    parser = argparse.ArgumentParser(description="Simulate an ADS-B flooding attack.")
    parser.add_argument("--rate", type=int, default=500)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--fixed-icao", action="store_true")
    parser.add_argument("--output", type=str, default="-")
    parser.add_argument("--rssi-base", type=float, default=-18.0)
    args = parser.parse_args()

    if args.output == "-" or args.output.lower() == "stdout":
        out = sys.stdout
        close_out = False
    else:
        out = open(args.output, "w", buffering=1)
        close_out = True

    fixed_icao_value = random_icao() if args.fixed_icao else None
    total_msgs = args.rate * args.duration
    interval = 1.0 / args.rate if args.rate > 0 else 0.0

    start_time = time.time()
    sent = 0

    try:
        while sent < total_msgs:
            msg = generate_message(icao=fixed_icao_value, rssi_base=args.rssi_base)
            out.write(json.dumps(msg) + "\n")
            sent += 1
            if interval > 0:
                elapsed = time.time() - start_time
                expected = sent * interval
                if expected > elapsed:
                    time.sleep(expected - elapsed)
    finally:
        if close_out:
            out.close()

if __name__ == "__main__":
    main()
