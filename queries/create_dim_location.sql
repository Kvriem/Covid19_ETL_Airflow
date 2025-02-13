CREATE TABLE IF NOT EXISTS dim_location (
    location_id SERIAL PRIMARY KEY,
    fips VARCHAR(10),
    admin2 VARCHAR(255),
    province_state VARCHAR(255),
    country_region VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT,
    combined_key VARCHAR(500)
);