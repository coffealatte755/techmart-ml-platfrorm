#!/usr/bin/env bash
# Build image Docker aplikasi TechMart dan push ke ECR.
# Usage: bash scripts/build_and_push_ecr.sh <province> <name>
set -euo pipefail

PROVINCE="${1:?Usage: build_and_push_ecr.sh <province> <name>}"
NAME="${2:?Usage: build_and_push_ecr.sh <province> <name>}"
REGION="us-east-1"
REPO_NAME="techmart-ecr-${PROVINCE}-${NAME}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Pastikan repo ECR ada (biasanya sudah dibuat oleh CloudFormation stack ECS,
# tapi kita buat manual dulu jika deploy image dilakukan sebelum stack ECS).
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

docker build -t "${REPO_NAME}:latest" ./app
docker tag "${REPO_NAME}:latest" "${REGISTRY}/${REPO_NAME}:latest"
docker push "${REGISTRY}/${REPO_NAME}:latest"

echo "Image pushed: ${REGISTRY}/${REPO_NAME}:latest"
