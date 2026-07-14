"""
TechMart - Synthetic Dataset Generator
=======================================
Menghasilkan 4 dataset sintetis untuk simulasi platform e-commerce:
  - user_profiles.csv
  - product_catalog.csv
  - user_interactions.csv
  - transaction_history.csv

Lalu mengunggah semuanya ke folder raw-data/ pada bucket S3 data lake.

Cara pakai:
    pip install -r requirements.txt   # faker, pandas, numpy, boto3
    python generate_datasets.py \
        --bucket techmart-ml-<province>-<name> \
        --num-users 5000 \
        --num-products 1000 \
        --num-interactions 50000 \
        --num-transactions 15000 \
        --seed 42
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import boto3
from faker import Faker

CATEGORIES = [
    "Electronics", "Fashion", "Home & Living", "Beauty", "Sports",
    "Books", "Toys", "Groceries", "Automotive", "Health",
]
BRANDS = ["Aurora", "Nimbus", "Vertex", "Orbit", "Solace", "Kinetic",
          "Lumen", "Zenith", "Fable", "Cascade"]
INTERACTION_TYPES = ["view", "like", "add_to_cart", "purchase"]
PAYMENT_METHODS = ["credit_card", "debit_card", "e_wallet", "bank_transfer", "cod"]
DELIVERY_STATUS = ["processing", "shipped", "delivered", "returned", "cancelled"]
INDONESIA_PROVINCES = [
    "DKI Jakarta", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Bali",
    "Kepulauan Riau", "Sumatera Utara", "Sulawesi Selatan", "Kalimantan Timur",
    "Yogyakarta",
]


def generate_user_profiles(fake: Faker, n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        signup_date = fake.date_time_between(start_date="-3y", end_date="-1d")
        rows.append({
            "user_id": f"U{i:07d}",
            "full_name": fake.name(),
            "email": fake.unique.email(),
            "gender": random.choice(["M", "F"]),
            "age": random.randint(17, 65),
            "province": random.choice(INDONESIA_PROVINCES),
            "city": fake.city(),
            "signup_date": signup_date.isoformat(),
            "customer_segment": random.choices(
                ["new", "regular", "loyal", "vip"], weights=[0.3, 0.4, 0.2, 0.1]
            )[0],
            "preferred_category": random.choice(CATEGORIES),
        })
    return pd.DataFrame(rows)


def generate_product_catalog(fake: Faker, n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        category = random.choice(CATEGORIES)
        price = round(np.random.lognormal(mean=11, sigma=1.0), -2)
        rows.append({
            "product_id": f"P{i:06d}",
            "product_name": fake.catch_phrase(),
            "category": category,
            "brand": random.choice(BRANDS),
            "price": max(price, 5000),
            "stock": random.randint(0, 500),
            "rating": round(random.uniform(2.5, 5.0), 1),
            "is_available": random.choices([True, False], weights=[0.9, 0.1])[0],
            "created_at": fake.date_time_between(start_date="-2y", end_date="-1d").isoformat(),
        })
    return pd.DataFrame(rows)


def generate_user_interactions(users: pd.DataFrame, products: pd.DataFrame, n: int) -> pd.DataFrame:
    user_ids = users["user_id"].tolist()
    product_ids = products["product_id"].tolist()
    rows = []
    for i in range(n):
        ts = datetime.now() - timedelta(days=random.randint(0, 365),
                                         seconds=random.randint(0, 86400))
        rows.append({
            "interaction_id": str(uuid.uuid4()),
            "user_id": random.choice(user_ids),
            "product_id": random.choice(product_ids),
            "interaction_type": random.choices(
                INTERACTION_TYPES, weights=[0.6, 0.15, 0.15, 0.10]
            )[0],
            "timestamp": ts.isoformat(),
            "session_id": str(uuid.uuid4())[:8],
        })
    return pd.DataFrame(rows)


def generate_transaction_history(users: pd.DataFrame, products: pd.DataFrame, n: int) -> pd.DataFrame:
    user_ids = users["user_id"].tolist()
    prod_lookup = products.set_index("product_id")["price"].to_dict()
    product_ids = list(prod_lookup.keys())
    rows = []
    for i in range(n):
        pid = random.choice(product_ids)
        qty = random.randint(1, 5)
        price = prod_lookup[pid]
        discount = round(random.choice([0, 0, 0.05, 0.1, 0.15, 0.2]) * price * qty, 2)
        ts = datetime.now() - timedelta(days=random.randint(0, 365))
        rows.append({
            "transaction_id": f"T{i:08d}",
            "user_id": random.choice(user_ids),
            "product_id": pid,
            "quantity": qty,
            "unit_price": price,
            "discount": discount,
            "total_amount": round(price * qty - discount, 2),
            "payment_method": random.choice(PAYMENT_METHODS),
            "delivery_status": random.choice(DELIVERY_STATUS),
            "transaction_date": ts.isoformat(),
        })
    return pd.DataFrame(rows)


def upload_to_s3(local_path: str, bucket: str, key: str):
    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} -> s3://{bucket}/{key}")


def main():
    parser = argparse.ArgumentParser(description="Generate TechMart synthetic datasets")
    parser.add_argument("--bucket", required=True, help="Nama bucket S3 data lake")
    parser.add_argument("--num-users", type=int, default=5000)
    parser.add_argument("--num-products", type=int, default=1000)
    parser.add_argument("--num-interactions", type=int, default=50000)
    parser.add_argument("--num-transactions", type=int, default=15000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--skip-upload", action="store_true", help="Hanya generate lokal, tidak upload")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    fake = Faker()
    Faker.seed(args.seed)

    import os
    os.makedirs(args.output_dir, exist_ok=True)

    print("Generating user_profiles...")
    users = generate_user_profiles(fake, args.num_users)
    print("Generating product_catalog...")
    products = generate_product_catalog(fake, args.num_products)
    print("Generating user_interactions...")
    interactions = generate_user_interactions(users, products, args.num_interactions)
    print("Generating transaction_history...")
    transactions = generate_transaction_history(users, products, args.num_transactions)

    files = {
        "user_profiles.csv": users,
        "product_catalog.csv": products,
        "user_interactions.csv": interactions,
        "transaction_history.csv": transactions,
    }

    for filename, df in files.items():
        local_path = f"{args.output_dir}/{filename}"
        df.to_csv(local_path, index=False)
        print(f"Saved {local_path} ({len(df)} rows)")
        if not args.skip_upload:
            upload_to_s3(local_path, args.bucket, f"raw-data/{filename}")

    print("Done.")


if __name__ == "__main__":
    main()
