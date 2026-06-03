"""
import_curated_vessels.py
Imports a curated list of active shadow fleet vessels into the DarkFleet database.
"""

import psycopg2

DB_CONFIG = {
    "dbname":   "darkfleet",
    "user":     "postgres",
    "password": "Ostenfeld35",
    "host":     "localhost",
    "port":     5432,
}

VESSELS = [
    # name, mmsi, imo, flag, type, owner, sanctions_list, reason
    ("NOVATOR",            "273272530", "IMO9297357", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Crude oil tanker, EU+UK+OFAC sanctioned, active East Asia"),
    ("UNIVERSAL",          "273271630", "IMO9384306", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Chemical/oil tanker, OFAC+EU+UK sanctioned, active NW Atlantic"),
    ("IMMANUEL",           "273378220", "IMO9056571", "RU", "Tanker",  "Sovcomflot",                  "EU",   "Oil products tanker, EU+UK sanctioned, active East Asia"),
    ("DOBRYNYA",           "273449240", "IMO9187617", "RU", "Tanker",  "Unknown",                     "OFAC", "Active Sakhalin Russia, RUSSIA-EO14024"),
    ("KARTHA",             "667001798", "IMO9285449", "SL", "Tanker",  "Gatik Ship Management",       "OFAC", "Ex-BARON, active Atlantic, multi-sanctioned"),
    ("MYSTERY",            "667001245", "IMO9332834", "SL", "Tanker",  "Han Jiang Shipmanagement",    "OFAC", "Ex-SOORAJ, 5+ name and flag changes, active Arabian Sea"),
    ("PHOENIX",            "273270560", "IMO9332810", "RU", "Tanker",  "Unknown",                     "EU",   "Ex-BORACAY/PUSHPA, 8+ flag changes, boarded by France Sept 2025"),
    ("IVAN AIVAZOVSKY",    "273257370", "IMO9876359", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Products tanker, RUSSIA-EO14024 Jan 2025 sanctions"),
    ("MIKHAIL ULYANOV",    "273328440", "IMO9333670", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Arctic shuttle tanker, Prirazlomnaya platform, RUSSIA-EO14024"),
    ("KIRILL LAVROV",      "273329060", "IMO9333682", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Arctic shuttle tanker, Prirazlomnaya platform, RUSSIA-EO14024"),
    ("VOSTOCHNY PROSPECT", "273611590", "IMO9866392", "RU", "Tanker",  "Sovcomflot",                  "OFAC", "Sovcomflot crude tanker, active Ust-Luga route"),
    ("BAVLY",              "273358180", "IMO9621560", "RU", "Tanker",  "Unknown",                     "EU",   "Black Sea tanker, active Dec 2025"),
    ("SIG",                "273340190", "IMO9735335", "RU", "Tanker",  "Unknown",                     "OFAC", "Black Sea tanker, active"),
    ("VF TANKER-4",        "273354450", "IMO9640528", "RU", "Tanker",  "VF Tanker",                   "EU",   "Oil products tanker, Black Sea active"),
    ("EVENTIN",            "211146780", "IMO9308065", "DE", "Tanker",  "Unknown",                     "EU",   "Drifted disabled in Baltic Jan 2025 with 100k tons Russian oil"),
    ("TANGO",              "518100626", "IMO9292211", "PW", "Yacht",   "Viktor Vekselberg",           "OFAC", "Vekselberg superyacht, seized Mallorca April 2022"),
    ("SPARTA II",          "273394890", "IMO9160994", "RU", "Cargo",   "Oboronlogistika",             "OFAC", "Russian military RoRo vessel, English Channel Feb 2026"),
    ("GENERAL SKOBELEV",   "273335920", "IMO9503304", "RU", "Cargo",   "Russian Ministry of Defence", "EU",   "Russian military logistics, escorted by Dutch navy Jan 2026"),
    ("GRACEFUL",           "273310900", "IMO9153850", "RU", "Yacht",   "Russian Government",          "OFAC", "Putin-linked yacht, left Hamburg abruptly Feb 2022"),
    ("DILBAR",             "319057900", "IMO1012376", "KY", "Yacht",   "Alisher Usmanov",             "OFAC", "Usmanov superyacht 156m, seized Germany March 2022"),
    ("AMADEA",             "319016900", "IMO1012552", "KY", "Yacht",   "Suleyman Kerimov",            "OFAC", "Kerimov superyacht, seized Fiji May 2022, now US custody"),
    ("CRESCENT",           "319904000", "IMO9750648", "KY", "Yacht",   "Igor Sechin (Rosneft CEO)",   "EU",   "Sechin superyacht 135m, seized Spain March 2022"),
    ("AMORE VERO",         "227127000", "IMO9684059", "FR", "Yacht",   "Igor Sechin (Rosneft CEO)",   "EU",   "Sechin superyacht, seized France March 2022"),
    ("SCHEHERAZADE",       "319111700", "IMO1012553", "KY", "Yacht",   "Unknown (Putin-linked)",      "EU",   "Putin-linked superyacht, investigated by Italian authorities"),
    ("LUNA",               "319173000", "IMO1012374", "KY", "Yacht",   "Farkhad Akhmedov",            "UK",   "Akhmedov superyacht, UK sanctioned"),
]


def main():
    print("DarkFleet — importing curated vessels\n")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    for vtype in set(v[4] for v in VESSELS):
        cur.execute("INSERT INTO vessel_type (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (vtype,))

    inserted = 0
    updated = 0

    for (name, mmsi, imo, flag, vtype, owner, sanction_list, reason) in VESSELS:
        cur.execute("SELECT id FROM vessel_type WHERE name = %s", (vtype,))
        type_id = cur.fetchone()[0]

        cur.execute("SELECT id FROM vessel WHERE mmsi = %s", (mmsi,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM vessel WHERE imo_number = %s", (imo,))
            row = cur.fetchone()

        if row:
            vessel_id = row[0]
            cur.execute("""
                UPDATE vessel SET name=%s, mmsi=%s, imo_number=%s,
                current_flag=%s, owner=%s, vessel_type_id=%s WHERE id=%s
            """, (name, mmsi, imo, flag, owner, type_id, vessel_id))
            updated += 1
            print(f"Updated: {name:25s} MMSI={mmsi}")
        else:
            cur.execute("""
                INSERT INTO vessel (mmsi, imo_number, name, current_flag, owner, vessel_type_id)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
            """, (mmsi, imo, name, flag, owner, type_id))
            vessel_id = cur.fetchone()[0]
            inserted += 1
            print(f"Inserted: {name:25s} MMSI={mmsi}")

        cur.execute("""
            SELECT se.id FROM sanction_entry se
            JOIN vessel_sanction vs ON vs.sanction_entry_id = se.id
            WHERE vs.vessel_id = %s AND se.list_source = %s
        """, (vessel_id, sanction_list))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO sanction_entry (entity_name, list_source, reason) VALUES (%s,%s,%s) RETURNING id",
                (name, sanction_list, reason)
            )
            sanction_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO vessel_sanction (vessel_id, sanction_entry_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (vessel_id, sanction_id)
            )

        cur.execute(
            "SELECT id FROM suspicion_event WHERE vessel_id=%s AND rule_name='sanctioned_vessel'",
            (vessel_id,)
        )
        if not cur.fetchone():
            weight = 50 if vtype == "Yacht" else 40
            cur.execute(
                "INSERT INTO suspicion_event (vessel_id, rule_name, weight, description) VALUES (%s,'sanctioned_vessel',%s,%s)",
                (vessel_id, weight, f"Listed on {sanction_list}: {reason[:200]}")
            )

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Inserted: {inserted}  Updated: {updated}")


if __name__ == "__main__":
    main()