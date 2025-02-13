from airflow import DAG
from datetime import datetime, timedelta
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
import pandas as pd
from sqlalchemy import create_engine
from airflow.hooks.base import BaseHook
import logging

DEFAULT_DATE = datetime(2020, 1, 22).date()  # First available data date

def extract_data_from_github(ti):
    """Extracts COVID-19 data from GitHub for the next available date."""
    conn = BaseHook.get_connection('postgres_conn')
    engine = create_engine(f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}")

    # Get last processed date from database
    try:
        result = engine.execute("SELECT MAX(date) FROM dim_date_details;")
        last_date = result.fetchone()[0]
    except Exception as e:
        logging.error(f"Error querying max date: {e}")
        last_date = None

    current_date = last_date + timedelta(days=1) if last_date else DEFAULT_DATE
    today = datetime.today().date()

    while current_date <= today:
        date_str = current_date.strftime("%m-%d-%Y")
        url = f'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/{date_str}.csv'
        logging.info(f"Trying {url}")

        try:
            df = pd.read_csv(url)
            # Standardize column names with explicit mappings
            df.columns = df.columns.str.strip().str.lower().str.replace('[^a-z0-9]', '_', regex=True).str.replace('__+', '_', regex=True)

            # Handle known column name variations from historical data
            column_mapping = {
                'province_state': ['province', 'state'],
                'country_region': ['country'],
                'lat': ['latitude'],
                'long_': ['longitude', 'lng']
            }

            for standard_col, alt_cols in column_mapping.items():
                for alt in alt_cols:
                    if alt in df.columns and standard_col not in df.columns:
                        df.rename(columns={alt: standard_col}, inplace=True)

            ti.xcom_push(key='raw_data', value=df.to_json())
            logging.info(f"Successfully fetched data for {current_date}")
            return
        except Exception as e:
            logging.warning(f"Failed to fetch {current_date}: {e}")
            current_date += timedelta(days=1)

    raise ValueError("No new data available up to today's date.")

def transform_data(ti):
    """Transforms raw data and prepares dimensional models."""
    raw_data = ti.xcom_pull(task_ids='extract_data', key='raw_data')
    df = pd.read_json(raw_data)

    # Process last_update to date
    df['last_update'] = pd.to_datetime(df['last_update']).dt.date

    # Ensure required columns for combined_key
    required_keys = ['province_state', 'country_region']
    for col in required_keys:
        if col not in df.columns:
            df[col] = df.get(col, '')  # Fallback to empty string

    # Generate combined_key
    df['combined_key'] = df.apply(
        lambda row: f"{row.get('admin2', '')}, {row.get('province_state', '')}, {row.get('country_region', '')}".strip(', '),
        axis=1
    )

    # Define numerical columns and fill missing ones
    num_cols = ['confirmed', 'deaths', 'recovered', 'active', 'incident_rate', 'case_fatality_ratio']
    for col in num_cols:
        if col not in df.columns:
            df[col] = 0
    df[num_cols] = df[num_cols].fillna(0)

    # Create date dimension based on unique last_update dates
    unique_dates = df['last_update'].unique()
    dim_date_details = pd.DataFrame({
        'date': unique_dates,
        'year': [d.year for d in unique_dates],
        'month': [d.month for d in unique_dates],
        'day': [d.day for d in unique_dates],
        'weekday': [d.strftime("%A") for d in unique_dates],
        'is_weekend': [d.strftime("%A") in ['Saturday', 'Sunday'] for d in unique_dates]
    })

    # Ensure required columns exist for the location dimension
    required_columns = ['fips', 'admin2', 'lat', 'long_']
    for col in required_columns:
        if col not in df.columns:
            df[col] = None

    dim_location_details = df[['fips', 'admin2', 'province_state', 'country_region', 'lat', 'long_', 'combined_key']].drop_duplicates()

    # Create fact table using the standardized date
    fact_covid = df[['last_update', 'combined_key', 'confirmed', 'deaths', 'recovered', 'active', 'incident_rate', 'case_fatality_ratio']]

    # Push the transformed data to XCom
    ti.xcom_push(key='dim_date_details', value=dim_date_details.to_json(date_format='iso'))
    ti.xcom_push(key='dim_location_details', value=dim_location_details.to_json())
    ti.xcom_push(key='fact_covid', value=fact_covid.to_json())

def load_data_into_postgres(ti):
    """Loads transformed data into PostgreSQL with deduplication."""
    conn = BaseHook.get_connection('postgres_conn')
    engine = create_engine(f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}")

    # Pull transformed JSON data from XCom
    dim_date_json = ti.xcom_pull(task_ids='transform_data', key='dim_date_details')
    dim_loc_json = ti.xcom_pull(task_ids='transform_data', key='dim_location_details')
    fact_covid_json = ti.xcom_pull(task_ids='transform_data', key='fact_covid')

    if not (dim_date_json and dim_loc_json and fact_covid_json):
        raise ValueError("Missing transformed data in XCom.")

    # Convert JSON strings back to DataFrames
    dim_date_details = pd.read_json(dim_date_json)
    dim_date_details['date'] = pd.to_datetime(dim_date_details['date']).dt.date

    dim_location_details = pd.read_json(dim_loc_json)
    fact_covid = pd.read_json(fact_covid_json)
    fact_covid['last_update'] = pd.to_datetime(fact_covid['last_update']).dt.date

    with engine.begin() as connection:
        # Upsert date dimension
        existing_dates = pd.read_sql("SELECT date FROM dim_date_details", connection)
        existing_dates['date'] = pd.to_datetime(existing_dates['date']).dt.date
        new_dim_date = dim_date_details[~dim_date_details['date'].isin(existing_dates['date'])]
        if not new_dim_date.empty:
            new_dim_date.to_sql('dim_date_details', connection, if_exists='append', index=False)

        # Upsert location dimension
        existing_locations = pd.read_sql("SELECT combined_key FROM dim_location_details", connection)
        new_dim_location = dim_location_details[~dim_location_details['combined_key'].isin(existing_locations['combined_key'])]
        if not new_dim_location.empty:
            new_dim_location.to_sql('dim_location_details', connection, if_exists='append', index=False)

        # Load fact data
        date_dim = pd.read_sql("SELECT date_id, date FROM dim_date_details", connection)
        location_dim = pd.read_sql("SELECT location_id, combined_key FROM dim_location_details", connection)

        fact_merged = fact_covid.merge(date_dim, left_on='last_update', right_on='date', how='left')
        fact_merged = fact_merged.merge(location_dim, on='combined_key', how='left')

        # Drop rows with missing foreign keys
        fact_final = fact_merged.dropna(subset=['date_id', 'location_id'])
        fact_final = fact_final[['date_id', 'location_id', 'confirmed', 'deaths', 'recovered', 'active', 'incident_rate', 'case_fatality_ratio']]

        if not fact_final.empty:
            fact_final.to_sql('fact_cases', connection, if_exists='append', index=False)

with DAG(
    'Covid19_ETL',
    description='COVID-19 data pipeline from GitHub to Postgres',
    start_date=datetime(2023, 1, 1),
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1
) as dag:

    create_tables = PostgresOperator(
        task_id='create_tables',
        postgres_conn_id='postgres_conn',
        sql='''
        CREATE TABLE IF NOT EXISTS dim_date_details (
            date_id SERIAL PRIMARY KEY,
            date DATE UNIQUE NOT NULL,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            weekday VARCHAR(9),
            is_weekend BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS dim_location_details (
            location_id SERIAL PRIMARY KEY,
            fips VARCHAR(10),
            admin2 VARCHAR(255),
            province_state VARCHAR(255),
            country_region VARCHAR(255),
            lat FLOAT,
            long_ FLOAT,
            combined_key VARCHAR(500) UNIQUE
        );

        CREATE TABLE IF NOT EXISTS fact_cases (
            case_id SERIAL PRIMARY KEY,
            date_id INTEGER REFERENCES dim_date_details(date_id),
            location_id INTEGER REFERENCES dim_location_details(location_id),
            confirmed INTEGER,
            deaths INTEGER,
            recovered INTEGER,
            active INTEGER,
            incident_rate FLOAT,
            case_fatality_ratio FLOAT
        );
        '''
    )

    extract = PythonOperator(
        task_id='extract_data',
        python_callable=extract_data_from_github
    )

    transform = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data
    )

    load = PythonOperator(
        task_id='load_data',
        python_callable=load_data_into_postgres
    )

    create_tables >> extract >> transform >> load