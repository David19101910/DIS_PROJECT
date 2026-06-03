-- DarkFleet, schema.sql
-- Run with: psql -U postgres -d darkfleet -f schema.sql

-- 1. VESSEL TYPE
CREATE TABLE IF NOT EXISTS vessel_type (
    id SERIAL PRIMARY KEY,
    name  VARCHAR(50) NOT NULL UNIQUE
);

-- 2. VESSEL
CREATE TABLE IF NOT EXISTS vessel (
    id SERIAL PRIMARY KEY,
    mmsi CHAR(9)     UNIQUE,
    imo_number VARCHAR(10) UNIQUE,
    name  VARCHAR(100),
    current_flag CHAR(2),
    owner VARCHAR(100),
    vessel_type_id INT REFERENCES vessel_type(id),

    CONSTRAINT mmsi_format CHECK (mmsi IS NULL OR mmsi ~ '^\d{9}$'),
    CONSTRAINT imo_format  CHECK (imo_number IS NULL OR imo_number ~ '^IMO\d{7}$'),
    CONSTRAINT flag_format CHECK (current_flag IS NULL OR current_flag ~ '^[A-Z]{2}$')
);

-- 3. POSITION
CREATE TABLE IF NOT EXISTS position (
    id SERIAL PRIMARY KEY,
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_knots REAL,
    heading REAL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_position_vessel_time
    ON position(vessel_id, recorded_at DESC);

-- 4. AIS_GAP
CREATE TABLE IF NOT EXISTS ais_gap (
    id SERIAL PRIMARY KEY,
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    gap_start TIMESTAMPTZ NOT NULL,
    gap_end TIMESTAMPTZ NOT NULL,
    gap_hours REAL GENERATED ALWAYS AS
                            (EXTRACT(EPOCH FROM (gap_end - gap_start)) / 3600) STORED,
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION,
    reappear_lat DOUBLE PRECISION,
    reappear_lon DOUBLE PRECISION,
    distance_jumped_nm REAL,

    CONSTRAINT gap_order CHECK (gap_end > gap_start)
);

-- 5. FLAG_CHANGE
CREATE TABLE IF NOT EXISTS flag_change (
    id SERIAL PRIMARY KEY,
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    flag_from CHAR(2) NOT NULL,
    flag_to     CHAR(2) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT flag_from_format CHECK (flag_from ~ '^[A-Z]{2}$'),
    CONSTRAINT flag_to_format   CHECK (flag_to   ~ '^[A-Z]{2}$'),
    CONSTRAINT flag_changed     CHECK (flag_from <> flag_to)
);

-- 6. SANCTION_ENTRY
CREATE TABLE IF NOT EXISTS sanction_entry (
    id SERIAL PRIMARY KEY,
    entity_name VARCHAR(200) NOT NULL,
    list_source VARCHAR(20)  NOT NULL CHECK (list_source IN ('OFAC','EU','UK')),
    reason TEXT,
    listed_since DATE
);

CREATE TABLE IF NOT EXISTS vessel_sanction (
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    sanction_entry_id INT NOT NULL REFERENCES sanction_entry(id) ON DELETE CASCADE,
    PRIMARY KEY (vessel_id, sanction_entry_id)
);

-- 7. SUSPICION_EVENT
CREATE TABLE IF NOT EXISTS suspicion_event (
    id SERIAL PRIMARY KEY,
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    weight INT NOT NULL CHECK (weight > 0),
    description TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. USERS
CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);

-- 9. FAVORITES
CREATE TABLE IF NOT EXISTS favorites (
    username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    vessel_id INT NOT NULL REFERENCES vessel(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (username, vessel_id)
);

-- 10. VIEW: suspicion score per vessel
CREATE OR REPLACE VIEW suspicion_score AS
SELECT
    v.id AS vessel_id,
    v.mmsi,
    v.name,
    v.current_flag,
    COALESCE(SUM(se.weight), 0) AS total_score,
    CASE
        WHEN COALESCE(SUM(se.weight), 0) >= 51 THEN 'HIGH RISK'
        WHEN COALESCE(SUM(se.weight), 0) >= 21 THEN 'SUSPICIOUS'
        ELSE 'CLEAN'
    END AS risk_level
FROM vessel v
LEFT JOIN suspicion_event se ON se.vessel_id = v.id
GROUP BY v.id, v.mmsi, v.name, v.current_flag
ORDER BY total_score DESC;

-- 11. SEED DATA
INSERT INTO vessel_type (name) VALUES
    ('Tanker'),
    ('Bulk Carrier'),
    ('Cargo'),
    ('Yacht'),
    ('Container Ship'),
    ('LNG Tanker')
ON CONFLICT DO NOTHING;