FROM apache/airflow:2.10.4

# Switch to the 'airflow' user before installing pandas
USER airflow
RUN pip install pandas
