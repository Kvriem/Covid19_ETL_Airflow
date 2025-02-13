CREATE TABLE IF NOT EXISTS fact_covid_cases (
    case_id SERIAL PRIMARY KEY,
    date_id INTEGER REFERENCES dim_date(date_id),
    location_id INTEGER REFERENCES dim_location(location_id),
    confirmed INTEGER,
    deaths INTEGER,
    recovered INTEGER,
    active INTEGER,
    incident_rate FLOAT,
    case_fatality_ratio FLOAT
);