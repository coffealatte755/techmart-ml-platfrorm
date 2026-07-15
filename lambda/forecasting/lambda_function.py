"""
techmart-ml-forecasting
=========================
Lambda untuk menghasilkan prediksi time-series sederhana (mis. demand
forecasting per produk) berbasis moving-average dari histori interaksi/
transaksi yang sudah diringkas ke dalam model artefak.

Trigger: API Gateway (POST /forecasts), Lambda proxy integration.
Input JSON:  {"product_id": "P000123", "horizon_days": 7}
Output JSON: {"product_id": ..., "forecast": [{"day": 1, "expected_demand": ...}, ...]}
"""

import json
import os
import pickle
import time
import uuid

import boto3
import numpy as np

BUCKET_NAME = os.environ.get("BUCKET_NAME")
MODEL_KEY = os.environ.get("MODEL_KEY", "models/hybrid_model.pkl")
RESULT_TABLE = os.environ.get("RESULT_TABLE", "MLForecastResults")
LOCAL_MODEL_PATH = "/tmp/hybrid_model.pkl"

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

_MODEL_CACHE = {"model": None}


def _load_model():
    if _MODEL_CACHE["model"] is not None:
        return _MODEL_CACHE["model"]

    if not os.path.exists(LOCAL_MODEL_PATH):
        s3.download_file(BUCKET_NAME, MODEL_KEY, LOCAL_MODEL_PATH)

    with open(LOCAL_MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    _MODEL_CACHE["model"] = model
    return model


def _forecast_demand(model, product_id: str, horizon_days: int = 7):
    """
    Pendekatan ringan: gunakan norma vektor produk sebagai proxy popularitas,
    lalu proyeksikan dengan sedikit noise musiman untuk horizon N hari.
    Pada implementasi produksi, ganti dengan model time-series (Prophet/DeepAR)
    yang dilatih terpisah di SageMaker.
    """
    product_categories = model["product_categories"]
    if product_id not in product_categories:
        base_demand = 1.0
    else:
        pidx = product_categories.index(product_id)
        base_demand = float(np.linalg.norm(model["product_factors"][pidx])) * 20

    rng = np.random.default_rng(abs(hash(product_id)) % (2**32))
    forecast = []
    for day in range(1, horizon_days + 1):
        seasonal = 1 + 0.1 * np.sin(day / 7 * np.pi)
        noise = rng.normal(loc=0, scale=0.05)
        expected = max(base_demand * seasonal * (1 + noise), 0)
        forecast.append({"day": day, "expected_demand": round(expected, 2)})
    return forecast


def _log_result(request_id, payload, result):
    table = dynamodb.Table(RESULT_TABLE)
    table.put_item(Item={
        "request_id": request_id,
        "input": json.dumps(payload),
        "output": json.dumps(result),
        "timestamp": int(time.time()),
        "ttl": int(time.time()) + 24 * 3600,
    })


def lambda_handler(event, context):
    request_id = str(uuid.uuid4())
    try:
        body = json.loads(event.get("body") or "{}")
        product_id = body.get("product_id")
        horizon_days = int(body.get("horizon_days", 7))

        if not product_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "product_id wajib diisi"}),
            }

        model = _load_model()
        forecast = _forecast_demand(model, product_id, horizon_days)
        result = {"product_id": product_id, "forecast": forecast}

        _log_result(request_id, body, result)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    except Exception as exc:  # pragma: no cover
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc), "request_id": request_id}),
        }
