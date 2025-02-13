# COVID-19 Case Data Cleansing & Modeling

## **Overview**
This project provides daily and cumulative COVID-19 case, recovery, and death counts to assist medical facilities in resource planning, such as hospital bed allocation. The cleansed and modeled dataset allows public health officials to easily observe new daily cases and hospitalization trends.
---
## **Project Diagram**
![alt text](Covid19_ETL(1).png)
---

## **Business Goal**
- **Objective**: Deliver accurate, standardized COVID-19 data for effective resource management in medical facilities.
- **Key Insight**: A clean, structured dataset facilitates quick analysis of COVID-19 trends and supports strategic decision-making.

---

## **Data & Dataset Description**
- **Data Source**:
  - [Johns Hopkins CSSE COVID-19 Data](https://github.com/CSSEGISandData/COVID-19)
- **Data Format**: Multiple CSV files containing daily counts by region (cases, deaths, recoveries).
- **Challenges Addressed**:
  - Inconsistent country/state naming.
  - Negative corrections and missing values.
  - Partial data for some dates.

---

## **Project Architecture**

### **1. Ingestion**
- Utilized Python and Apache Airflow to automate the download of daily CSV files from the GitHub repository.

### **2. Data Cleansing**
- Converted all date columns to a standard `YYYY-MM-DD` format.
- Standardized location names (e.g., "US" to "United States").
- Handled missing and negative values through imputation and correction.

### **3. Data Modeling**
- Designed a **PostgreSQL** database schema with:
  - **fact_covid_cases** table: Contains daily counts of cases, deaths, and recoveries for each region.
  - **dim_date** table: Holds date information to enable time-series analysis.
  - **dim_location** table: Stores standardized region details.

### **4. Orchestration**
- Implemented an **Apache Airflow DAG** to automate the end-to-end pipeline:
  - **Tasks**:
    - Download data.
    - Clean and transform data.
    - Load data into PostgreSQL tables.
  - **Scheduling**: Configured to run daily to ensure up-to-date data.

---

## **Technologies Used**
- **Programming Language**: Python
- **Orchestration Tool**: Apache Airflow
- **Database**: PostgreSQL
- **Libraries**: Pandas, SQLAlchemy, psycopg2

---

## **Usage**
### **Setup Instructions**
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-repo/Covid19_ETL_Airflow.git
   ```
2. **Navigate to the Project Directory**:
   ```bash
   cd Covid19_ETL_Airflow
   ```
3. **Configure Airflow**:
   - Set up the Airflow home directory and initialize the database.
   ```bash
   export AIRFLOW_HOME=~/airflow
   airflow db init
   ```
   - Add the DAG to the `dags` folder.
4. **Run Airflow**:
   ```bash
   airflow webserver --port 8080
   airflow scheduler
   ```

### **Access Data in PostgreSQL**:
- Connect to PostgreSQL using your credentials and query the `fact_covid_cases`, `dim_date`, and `dim_location` tables for analysis.

---

*This project is part of my data engineering portfolio.*

