#!/usr/bin/env python3
"""
rate_limit_validator.py

Applies message-rate and RSSI anomaly detection to ADS-B-like JSON messages.
"""

import argparse
import json
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

WINDOW_SECONDS = 10.0

def parse_timestamp(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return time.time()

class RateLimitValidator:
    def __init__(self, per_icao_threshold=50, global_threshold=1000,
                 rssi_cluster_threshold=0.5, min_icaos_for_cluster=5,
                 window_seconds=WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self.per_icao_times = defaultdict(deque)
        self.global_times = deque()
        self.global_rssi = deque()
        self.per_icao_threshold = per_icao_threshold
        self.global_threshold = global_threshold
        self.rssi_cluster_threshold = rssi_cluster_threshold
        self.min_icaos_for_cluster = min_icaos_for_cluster

    def _prune_old(self, now):
        cutoff = now - self.window_seconds
        while self.global_times and self.global_times[0] < cutoff:
            self.global_times.popleft()
        for icao, dq in list(self.per_icao_times.items()):
            while dq and dq[0] < cutoff:
                dq.popleft()
            if not dq:
                del self.per_icao_times[icao]
        while self.global_rssi and self.global_rssi[0][0] < cutoff:
            self.global_rssi.popleft()

    def _check_rssi_cluster(self):
        if len(self.global_rssi) < self.min_icaos_for_cluster:
            return None
        icaos = {entry[1] for entry in self.global_rssi}
        if len(icaos) < self.min_icaos_for_cluster:
            return None
        rssis = [entry[2] for entry in self.global_rssi]
        spread = max(rssis) - min(rssis)
        if spread <= self.rssi_cluster_threshold:
            return {"type": "rssi_cluster", "distinct_icaos": len(icaos),
                    "rssi_min": min(rssis), "rssi_max": max(rssis),
                    "rssi_spread": spread}
        return None

    def process_message(self, msg):
        alerts = []
        icao = msg.get("icao")
        rssi = msg.get("rssi")
        ts_str = msg.get("timestamp")
        now = parse_timestamp(ts_str) if ts_str else time.time()

        self.global_times.append(now)
        if icao is not None:
            self.per_icao_times[icao].append(now)
        if rssi is not None and icao is not None:
            self.global_rssi.append((now, icao, float(rssi)))

        self._prune_old(now)

        if icao is not None:
            count = len(self.per_icao_times[icao])
            if count > self.per_icao_threshold:
                alerts.append({
                    "type": "per_icao_rate",
                    "icao": icao,
                    "count_in_window": count,
                    "window_seconds": self.window_seconds,
                    "threshold": self.per_icao_threshold,
                    "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
                })

        global_count = len(self.global_times)
        if global_count > self.global_threshold:
            alerts.append({
                "type": "global_rate",
                "total_count_in_window": global_count,
                "window_seconds": self.window_seconds,
                "threshold": self.global_threshold,
                "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
            })

        rssi_alert = self._check_rssi_cluster()
        if rssi_alert:
            rssi_alert["timestamp"] = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
            alerts.append(rssi_alert)

        return alerts

def main():
    parser = argparse.ArgumentParser(description="ADS-B anomaly detector.")
    parser.add_argument("--input", type=str, default="-")
    parser.add_argument("--alerts-output", type=str, default="-")
    parser.add_argument("--per-icao-threshold", type=int, default=50)
    parser.add_argument("--global-threshold", type=int, default=1000)
    parser.add_argument("--window-seconds", type=float, default=WINDOW_SECONDS)
    parser.add_argument("--rssi-cluster-threshold", type=float, default=0.75)
    parser.add_argument("--min-icaos-for-cluster", type=int, default=5)
    args = parser.parse_args()

    if args.input == "-" or args.input.lower() == "stdin":
        in_f = sys.stdin
        close_in = False
    else:
        in_f = open(args.input, "r"); close_in=True

    if args.alerts_output == "-" or args.alerts_output.lower() == "stdout":
        out_f = sys.stdout; close_out=False
    else:
        out_f = open(args.alerts_output, "w", buffering=1); close_out=True

    validator = RateLimitValidator(
        per_icao_threshold=args.per_icao_threshold,
        global_threshold=args.global_threshold,
        rssi_cluster_threshold=args.rssi_cluster_threshold,
        min_icaos_for_cluster=args.min_icaos_for_cluster,
        window_seconds=args.window_seconds
    )

    try:
        for line in in_f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except:
                continue

            alerts = validator.process_message(msg)
            for alert in alerts:
                record = {"alert": alert, "original_message": msg}
                out_f.write(json.dumps(record) + "\n")
    finally:
        if close_in: in_f.close()
        if close_out: out_f.close()

if __name__ == "__main__":
    main()
