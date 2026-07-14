#!/usr/bin/env bash
# Zip kode Lambda (prediction & forecasting) lalu upload ke S3.
# Usage: bash scripts/package_lambda.sh <bucket-name>
set -euo pipefail

BUCKET="${1:?Usage: package_lambda.sh <bucket-name>}"
REGION="us-east-1"
BUILD_DIR=$(mktemp -d)

for fn in prediction forecasting; do
  echo "Packaging techmart-ml-${fn}..."
  cp "lambda/${fn}/lambda_function.py" "$BUILD_DIR/"
  pip install boto3 numpy -t "$BUILD_DIR" --quiet --no-deps 2>/dev/null || true
  (cd "$BUILD_DIR" && zip -qr "${fn}.zip" .)
  aws s3 cp "$BUILD_DIR/${fn}.zip" "s3://${BUCKET}/lambda/${fn}.zip" --region "$REGION"
  rm -f "$BUILD_DIR/${fn}.zip" "$BUILD_DIR/lambda_function.py"
done

rm -rf "$BUILD_DIR"
echo "Selesai. Kode Lambda tersedia di s3://${BUCKET}/lambda/{prediction,forecasting}.zip"
