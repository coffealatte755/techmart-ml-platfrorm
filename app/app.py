"""
TechMart App — dijalankan sebagai container di ECS Fargate (port 5000),
berada di belakang ALB (techmart-alb) dengan blue/green target group.

Endpoint:
  GET  /health        -> health check untuk ALB target group
  GET  /               -> info dasar
  POST /recommend       -> memanggil API Gateway (techmart-ml-api) /predictions
  POST /forecast        -> memanggil API Gateway (techmart-ml-api) /forecasts
"""

import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

API_BASE_URL = os.environ.get("TECHMART_API_BASE_URL", "")
API_KEY = os.environ.get("TECHMART_API_KEY", "")


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/")
def index():
    return jsonify(
        service="techmart-app",
        version=os.environ.get("APP_VERSION", "1.0.0"),
        message="TechMart recommendation frontend service is running",
    )


@app.post("/recommend")
def recommend():
    payload = request.get_json(force=True)
    if not API_BASE_URL:
        return jsonify(error="TECHMART_API_BASE_URL belum dikonfigurasi"), 500

    resp = requests.post(
        f"{API_BASE_URL}/predictions",
        json=payload,
        headers={"x-api-key": API_KEY},
        timeout=10,
    )
    return jsonify(resp.json()), resp.status_code


@app.post("/forecast")
def forecast():
    payload = request.get_json(force=True)
    if not API_BASE_URL:
        return jsonify(error="TECHMART_API_BASE_URL belum dikonfigurasi"), 500

    resp = requests.post(
        f"{API_BASE_URL}/forecasts",
        json=payload,
        headers={"x-api-key": API_KEY},
        timeout=10,
    )
    return jsonify(resp.json()), resp.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
