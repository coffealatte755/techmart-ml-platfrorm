"""
techmart-ml-prediction
=======================
Lambda untuk inferensi rekomendasi produk on-demand.
Model hybrid (hasil training SageMaker) diunduh dari S3 sekali saat cold
start, disimpan/di-cache di /tmp, lalu dipakai berulang kali selama
lifecycle eksekusi Lambda aktif (warm start).

Trigger: API Gateway (POST /predictions), Lambda proxy integration.
Input JSON:  {"user_id": "U0000123", "top_n": 5}
Output JSON: {"user_id": ..., "recommendations": [{"product_id":..., "score":...}, ...]}
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
RESULT_TABLE = os.environ.get("RESULT_TABLE", "MLPredictionResults")
LOCAL_MODEL_PATH = "/tmp/hybrid_model.pkl"

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Cache di module scope -> bertahan antar invocation selama container warm
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


def _recommend(model, user_id: str, top_n: int = 5):
    user_categories = model["user_categories"]
    product_categories = model["product_categories"]

    if user_id not in user_categories:
        # Cold-start user: fallback ke produk paling populer secara global
        # (rata-rata skor content feature) — sederhana namun aman.
        fallback_scores = np.linalg.norm(model["content_features"], axis=1)
        top_idx = np.argsort(-fallback_scores)[:top_n]
        return [
            {"product_id": product_categories[i], "score": float(fallback_scores[i])}
            for i in top_idx
        ]

    uidx = user_categories.index(user_id)
    scores = model["user_factors"][uidx] @ model["product_factors"].T
    top_idx = np.argsort(-scores)[:top_n]
    return [
        {"product_id": product_categories[i], "score": float(scores[i])}
        for i in top_idx
    ]


def _log_result(request_id, payload, result):
    table = dynamodb.Table(RESULT_TABLE)
    table.put_item(Item={
        "request_id": request_id,
        "input": json.dumps(payload),
        "output": json.dumps(result),
        "timestamp": int(time.time()),
        "ttl": int(time.time()) + 24 * 3600,  # TTL 24 jam
    })


def lambda_handler(event, context):
    request_id = str(uuid.uuid4())
    try:
        body = json.loads(event.get("body") or "{}")
        user_id = body.get("user_id")
        top_n = int(body.get("top_n", 5))

        if not user_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "user_id wajib diisi"}),
            }

        model = _load_model()
        recommendations = _recommend(model, user_id, top_n)
        result = {"user_id": user_id, "recommendations": recommendations}

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
