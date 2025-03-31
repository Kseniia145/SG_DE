from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def fetch_exchange_rates():
    app_id = os.getenv('OPENEXCHANGE_APP_ID')
    url = f"https://openexchangerates.org/api/latest.json?app_id={app_id}&base=USD"
    response = requests.get(url)
    return response.json()['rates']

def convert_orders():
    rates = fetch_exchange_rates()

    src_conn = psycopg2.connect(
        host="postgres1", dbname="orders_db", user="user", password="password", port=5432
    )
    dst_conn = psycopg2.connect(
        host="postgres2", dbname="orders_eur_db", user="user", password="password", port=5432
    )

    src_cursor = src_conn.cursor()
    dst_cursor = dst_conn.cursor()

    dst_cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders_eur (
            order_id UUID PRIMARY KEY,
            customer_email TEXT,
            order_date TIMESTAMP,
            amount NUMERIC(10, 2),
            currency TEXT
        )
    """)

    src_cursor.execute("SELECT order_id, customer_email, order_date, amount, currency FROM orders")
    rows = src_cursor.fetchall()

    rows_to_insert = []
    for order_id, email, order_date, amount, currency in rows:
        if currency == 'EUR':
            amount_eur = amount
        else:
            try:
                rate_from = rates[currency]
                rate_to_eur = rates['EUR']
                amount_eur = round((float(amount) / rate_from) * rate_to_eur, 2)
                rows_to_insert.append((order_id, email, order_date, amount_eur, 'EUR'))
                # print(f"Converting {currency} amount: {amount}")
            except KeyError as e:
                # print(f"Currency {currency} missing in rates", e)
                continue
    
    dst_cursor.executemany("""
        INSERT INTO orders_eur (order_id, customer_email, order_date, amount, currency)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (order_id) DO UPDATE SET amount = EXCLUDED.amount
    """, rows_to_insert)

    dst_conn.commit()
    src_cursor.close()
    dst_cursor.close()
    src_conn.close()
    dst_conn.close()

default_args = {
    'start_date': days_ago(0),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG('convert_orders_to_EUR_dag', schedule_interval='@hourly', default_args=default_args, catchup=False) as dag:
    convert_task = PythonOperator(
        task_id='convert_orders',
        python_callable=convert_orders
    )
