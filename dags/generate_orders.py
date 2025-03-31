from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import uuid
import random
import psycopg2
from faker import Faker
import requests
import os
from dotenv import load_dotenv

load_dotenv()
fake = Faker()

def get_currency_list():
    app_id = os.getenv("OPENEXCHANGE_APP_ID")
    url = f"https://openexchangerates.org/api/currencies.json?app_id={app_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return list(response.json().keys())
    else:
        print("Could not fetch currency list")
        return ['USD', 'EUR', 'CLP', 'GBP', 'JPY']

def generate_orders():
    currencies = get_currency_list()

    conn = psycopg2.connect(
        host="postgres1", dbname="orders_db", user="user", password="password", port=5432
    )
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id UUID PRIMARY KEY,
            customer_email TEXT,
            order_date TIMESTAMP,
            amount NUMERIC(10, 2),
            currency TEXT
        )
    """)
    base_time = datetime.now() - timedelta(days=7)
    for _ in range(5000):
        order_id = str(uuid.uuid4())
        email = fake.email()
        order_date = base_time + timedelta(seconds=random.randint(0, 7*24*3600))
        amount = round(random.uniform(1, 1000), 2)
        currency = random.choice(currencies)
        cursor.execute("""
            INSERT INTO orders (order_id, customer_email, order_date, amount, currency)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, email, order_date, amount, currency))
    conn.commit()
    cursor.close()
    conn.close()

default_args = {
    'start_date': days_ago(0),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG('generate_orders_dag', schedule_interval='*/10 * * * *', default_args=default_args, catchup=False) as dag:
    task = PythonOperator(
        task_id='generate_orders',
        python_callable=generate_orders
    )
