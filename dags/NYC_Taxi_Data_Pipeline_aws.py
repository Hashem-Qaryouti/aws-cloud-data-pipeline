from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sdk import Variable
from datetime import datetime, timedelta
import pyarrow.parquet as pq
import pandas as pd
import requests
import io
import paths
import boto3

DEBUG = True
BUCKET_NAME = "amzn-s3-bucket-25"
BUCKET_RAW_DATA_FOLDER= paths.BUCKET_RAW_DATA_FOLDER

s3_client = boto3.client("s3")

def download_green_taxi_data():    
    """ This function downloads raw green taxi data into Google Cloud Storage
        
        Args:
            None
        
        Return:
            None
    """
    base_url=paths.NYC_Green_Taxi_Data_URL

    today = datetime.today()

    for i in range(12):
        # Compute year-month
        date = today.replace(day=1) - timedelta(days=30*i)
        year = date.year
        month = f"{date.month:02d}"

        # File details
        url = f"{base_url}{year}-{month}.parquet"
        s3_key = f"{BUCKET_RAW_DATA_FOLDER}/green_tripdata_{year}-{month}.parquet"

        # Skip if file already exists (avoid duplicates)
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            print(f"{s3_key} already exists, skipping")
            continue
        except s3_client.exceptions.ClientError:
            pass

        # Download file
        print(f"Downloading {url}")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to download {url}")
            continue

        # Upload to AWS S3
        print(f"Uploading to gs://{BUCKET_NAME}/{s3_key}")
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=response.content
        )

        print("All available files processed")


def handle_missing_columns(col, missing_files,df_dict):
    for file in missing_files:
        df = df_dict[file]
        if col not in df.columns:
            df[col] = pd.NA
            print(f"Added missing column '{col}' with NaN in {file}")

def handle_type_mismatch(col, types, df_dict):
    """ Cast mismatched column types to a common type (default: string)
    """
    for dtype, files in types.items():
        for file in files:
            df = df_dict[file]
            if col in df.columns:
                df[col] = df[col].astype(str)
                print(f"Converted {col} in {file} from {dtype} to string")




# Define default args
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
}

with DAG(
    dag_id='NYC_Taxi_Data_AWS',
    default_args=default_args,
    description='A pipeline to process NYC Data',
    schedule='@daily',  # runs daily
    start_date=datetime(2025, 9, 7),
    catchup=False,
) as dag:
    
    

    download_raw_data = PythonOperator(
        task_id='download_green_taxi_data',
        python_callable=download_green_taxi_data
    )
    
    download_raw_data