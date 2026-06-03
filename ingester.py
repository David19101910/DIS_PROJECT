"""
ingester.py

Connects to aisstream.io and listens for live AIS position reports
for all tracked vessels in the DarkFleet database.
"""

import asyncio
import websockets
import json
import psycopg2
import ssl
from datetime import datetime, timezone

AIS_API_KEY = "6181da28b1565cf456e5862266dd882e1307194e"

DB_CONFIG = {
    "dbname":   "darkfleet",
    "user":     "postgres",
    "password": "YOUR_PASSWORD",
    "host":     "localhost",
    "port":     5432,
}

AIS_URL    = "wss://stream.aisstream.io/v0/stream"
BATCH_SIZE = 50
LISTEN_SEC = 300


def get_tracked_mmsi():
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    cur.execute("SELECT mmsi, id FROM vessel WHERE mmsi IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    mmsi_map = {row[0].strip(): row[1] for row in rows}
    print(f"Tracking {len(mmsi_map)} sanctioned vessels with MMSI")
    return mmsi_map


def make_batches(mmsi_list, size):
    for i in range(0, len(mmsi_list), size):
        yield mmsi_list[i:i + size]


def save_position(cur, vessel_id, lat, lon, speed, heading):
    cur.execute("""
        INSERT INTO position (vessel_id, latitude, longitude, speed_knots, heading, recorded_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (vessel_id, lat, lon, speed, heading, datetime.now(timezone.utc)))


def check_for_gap(cur, vessel_id, lat, lon):
    cur.execute("""
        SELECT recorded_at, latitude, longitude
        FROM position
        WHERE vessel_id = %s
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (vessel_id,))
    last = cur.fetchone()
    if not last:
        return
    last_time, last_lat, last_lon = last
    now = datetime.now(timezone.utc)
    hours_since = (now - last_time).total_seconds() / 3600
    if hours_since >= 6:
        cur.execute("""
            INSERT INTO ais_gap
                (vessel_id, gap_start, gap_end, last_lat, last_lon, reappear_lat, reappear_lon)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (vessel_id, last_time, now, last_lat, last_lon, lat, lon))
        cur.execute("""
            INSERT INTO suspicion_event (vessel_id, rule_name, weight, description)
            VALUES (%s, %s, %s, %s)
        """, (
            vessel_id, "ais_gap_6h",
            20 if hours_since < 24 else 30,
            f"AIS gap of {hours_since:.1f} hours detected"
        ))
        print(f"AIS gap detected: vessel_id={vessel_id}, {hours_since:.1f} hours")


def update_vessel_info(cur, vessel_id, name, ship_type):
    if name:
        cur.execute("""
            UPDATE vessel SET name = %s
            WHERE id = %s AND (name IS NULL OR name = '')
        """, (name, vessel_id))
    if ship_type:
        if 80 <= ship_type <= 89:   type_name = 'Tanker'
        elif 70 <= ship_type <= 79: type_name = 'Cargo'
        elif 30 <= ship_type <= 39: type_name = 'Yacht'
        elif 60 <= ship_type <= 69: type_name = 'Passenger'
        else:                       type_name = None
        if type_name:
            cur.execute("""
                UPDATE vessel SET vessel_type_id = (
                    SELECT id FROM vessel_type WHERE name = %s
                ) WHERE id = %s AND vessel_type_id IS NULL
            """, (type_name, vessel_id))


def handle_message(msg_raw, mmsi_map):
    try:
        msg = json.loads(msg_raw)
    except json.JSONDecodeError:
        return
    if msg.get("MessageType") != "PositionReport":
        return

    meta      = msg.get("MetaData", {})
    payload   = msg.get("Message", {}).get("PositionReport", {})
    mmsi      = str(meta.get("MMSI", "")).strip()
    lat       = meta.get("latitude")
    lon       = meta.get("longitude")
    speed     = payload.get("Sog")
    heading   = payload.get("TrueHeading")
    name      = meta.get("ShipName", "").strip()
    ship_type = payload.get("ShipType")

    if mmsi not in mmsi_map or lat is None or lon is None:
        return

    vessel_id = mmsi_map[mmsi]
    conn_local = psycopg2.connect(**DB_CONFIG)
    cur = conn_local.cursor()
    try:
        check_for_gap(cur, vessel_id, lat, lon)
        save_position(cur, vessel_id, lat, lon, speed, heading)
        update_vessel_info(cur, vessel_id, name, ship_type)
        conn_local.commit()
        print(f"{name or mmsi:30s} lat={lat:.4f} lon={lon:.4f} speed={speed}")
    except Exception as e:
        conn_local.rollback()
        print(f"DB error for {mmsi}: {e}")
    finally:
        cur.close()
        conn_local.close()


async def run_ingester():
    mmsi_map  = get_tracked_mmsi()
    mmsi_list = list(mmsi_map.keys())

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    print(f"\nConnecting to aisstream.io...")
    print(f"Listening for {len(mmsi_list)} vessels")
    print(f"Press Ctrl+C to stop\n")

    while True:
        try:
            async with websockets.connect(AIS_URL, ping_interval=20, ssl=ssl_ctx) as ws:
                await ws.send(json.dumps({
                    "APIKey": AIS_API_KEY,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],
                    "FiltersShipMMSI": mmsi_list,
                    "FilterMessageTypes": ["PositionReport"]
                }))
                print("Connected and listening...\n")
                async for message in ws:
                    handle_message(message, mmsi_map)

        except websockets.exceptions.ConnectionClosed as e:
            print(f"\nConnection closed, retrying in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"\nError: {e}, retrying in 10s...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    print("DarkFleet Ingester\n")
    try:
        asyncio.run(run_ingester())
    except KeyboardInterrupt:
        print("\n\nIngester stopped.")
