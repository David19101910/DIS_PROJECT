# DarkFleet - Maritime Sanctions Intelligence

DarkFleet is a real-time web application for tracking sanctioned vessels, shadow fleet tankers, and oligarch superyachts. It connects to live AIS data streams and cross-references vessel positions with OFAC, EU, and UK sanctions lists.

BEFORE FOLLOWING THIS GUIDE: GO DOWN TO POINT 6 AND CONFIGURE DATABASE CREDENTIALS


# Prerequisites

- Python
- PostgreSQL

# Setup Instructions

# 1. Clone the repository

git clone https://github.com/David19101910/DIS_PROJECT.git or download the repository as a zip.
cd darkfleet

# 2. Install Python dependencies

pip install flask flask_bcrypt psycopg2-binary requests beautifulsoup4 websockets pandas


# 3. Create the database

Open pgAdmin or psql and create a new database called `darkfleet`:

- CREATE DATABASE darkfleet;


# 4. Initialize the schema

Run the schema file against the darkfleet database:

```bash
psql -U postgres -d darkfleet -f schema.sql
```

Or open `schema.sql` in pgAdmin's query Tool and click run.

# 5. Import curated vessels

```bash
python import_curated_vessels.py
```

Imports a hand-curated list of verified active vessels including Russian shadow fleet tankers, oligarch superyachts. Parts of these vessels have been tested running the app with their signals being on. The same number of vessels being active cannot of course be ensured.

# 6. Configure database credentials

Open `app.py`, `ingester.py`, and `import_curated_vessels.py` and set your PostgreSQL password in `DB_CONFIG`:

```python
DB_CONFIG = {
    "dbname":   "darkfleet",
    "user":     "postgres",
    "password": "YOUR_PASSWORD",  # ← change this
    "host":     "localhost",
    "port":     5432,
}
```

---

# Running the Application

# start the web app

```bash
python app.py
```

Open your browser at: **http://127.0.0.1:5000** or the address that pops up.

# Start the AIS ingester (optional, for live data)

In a separate terminal:

```bash
python ingester.py
```

The ingester connects to aisstream.io and continuously receives live AIS position reports for all tracked vessels. Leave it running in the background to accumulate position data. A free API key is already configured which should function, otherwise get your own at https://aisstream.io.

# How to Use the Application

# Search for vessels
Use the search bar at the top to search by:
- **Vessel name** - e.g. `KARTHA`, `TANGO`, `NORD`
- **MMSI number** - exactly 9 digits, e.g. `518100626`
- **IMO number** - e.g. `IMO9292211`

The app uses regex to automatically detect whether the input is an MMSI, IMO, or name.

# View vessel details
Click any vessel name to see:
- Vessel info (type, owner, flag, MMSI, IMO)
- Active sanctions (OFAC, EU, UK)
- Live position history
- AIS gaps (periods where the vessel went dark)
- Flag changes
- Suspicion events and total risk score

# Create an account
Click **Register** in the top right to create an account.

# Save favourites
When logged in, click **Save as favorite** on any vessel page to add it to your watchlist. View your watchlist under **Profile**.

# Change password
Under **Profile**, enter a new password and click **Update**.

---

## Database Schema

The database consists of 9 tables:

- **vessel** - core vessel entity
- **vessel_type** - lookup table
- **position** - AIS position
- **ais_gap** - detected dark periods
- **flag_change** - logged flag changes
- **sanction_entry** - entries from sanctions lists
- **vessel_sanction** - many-to-many link between vessels and sanctions
- **suspicion_event** - individual events giving risks score
- **users** - registered users
- **favorites** - user-saved vessels ( weak entity )

---

## Technical Notes

**Regex validation** is used in two places:
1. In `app.py` 
2. In `schema.sql`

**AIS data** — Live position data from aisstream.io, a free WebSocket API. The ingester filters by MMSI to only collect data for tracked vessels.
