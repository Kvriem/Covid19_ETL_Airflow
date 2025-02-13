CREATE TABLE IF NOT EXISTS dim_date (
    date_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    weekday VARCHAR(10),
    is_weekend BOOLEAN
);