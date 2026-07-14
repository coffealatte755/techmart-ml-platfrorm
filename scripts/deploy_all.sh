#!/usr/bin/env bash
# TechMart - Deploy semua CloudFormation stack secara berurutan.
# Jalankan dari root repo: bash scripts/deploy_all.sh
set -euo pipefail

REGION="us-east-1"
PARAMS_FILE="cloudformation/00-parameters.yaml"

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "Buat dulu $PARAMS_FILE dari 00-parameters.yaml.sample" >&2
  exit 1
fi

PROVINCE=$(grep ProvinceName "$PARAMS_FILE" | awk '{print $2}')
NAME=$(grep StudentName "$PARAMS_FILE" | awk '{print $2}')
EMAIL=$(grep NotificationEmail "$PARAMS_FILE" | awk '{print $2}')
NAT_AMI=$(grep NatInstanceAmiId "$PARAMS_FILE" | awk '{print $2}')
INSTANCE_TYPE=$(grep DefaultInstanceType "$PARAMS_FILE" | awk '{print $2}')
LOGS_CIDR=$(grep LogsWhitelistCidr "$PARAMS_FILE" | awk '{print $2}')

BUCKET="techmart-ml-${PROVINCE}-${NAME}"

echo "== 1/9 Networking =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-networking \
  --template-file cloudformation/01-networking.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" \
    NatInstanceAmiId="$NAT_AMI" DefaultInstanceType="$INSTANCE_TYPE" \
  --capabilities CAPABILITY_NAMED_IAM

echo "== 2/9 S3 Data Lake =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-s3 \
  --template-file cloudformation/02-s3.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" \
    LogsWhitelistCidr="$LOGS_CIDR"

echo "== Membuat struktur folder di bucket (raw-data, processed-data, logs, models) =="
for prefix in raw-data processed-data logs models scripts tmp; do
  aws s3api put-object --bucket "$BUCKET" --key "${prefix}/" --region "$REGION" || true
done

echo ">> Sekarang jalankan dataset generator lalu upload script Glue:"
echo "   python dataset-generation/generate_datasets.py --bucket $BUCKET"
echo "   aws s3 cp glue-etl/techmart_etl_job.py s3://$BUCKET/scripts/techmart_etl_job.py"
read -rp "Tekan ENTER jika kedua langkah di atas sudah selesai..."

echo "== 3/9 DynamoDB =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-dynamodb \
  --template-file cloudformation/03-dynamodb.yaml

echo "== 4/9 Glue (Database, Crawler, ETL Job) =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-glue \
  --template-file cloudformation/04-glue.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" \
    DataLakeBucketName="$BUCKET" \
    GlueScriptS3Path="s3://$BUCKET/scripts/techmart_etl_job.py" \
  --capabilities CAPABILITY_NAMED_IAM

echo "== 5/9 SageMaker Notebook =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-sagemaker \
  --template-file cloudformation/05-sagemaker.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" \
  --capabilities CAPABILITY_NAMED_IAM

echo ">> Jalankan crawler, ETL job, lalu training notebook sebelum lanjut ke Lambda."
read -rp "Tekan ENTER jika model hybrid_model.pkl sudah ada di s3://$BUCKET/models/..."

echo "== Package & upload kode Lambda =="
bash scripts/package_lambda.sh "$BUCKET"

echo "== 6/9 Lambda =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-lambda \
  --template-file cloudformation/06-lambda.yaml \
  --parameter-overrides DataLakeBucketName="$BUCKET" LambdaCodeS3Bucket="$BUCKET" \
  --capabilities CAPABILITY_NAMED_IAM

PRED_ARN=$(aws cloudformation describe-stacks --region "$REGION" \
  --stack-name techmart-lambda \
  --query "Stacks[0].Outputs[?OutputKey=='PredictionFunctionArn'].OutputValue" --output text)
FORE_ARN=$(aws cloudformation describe-stacks --region "$REGION" \
  --stack-name techmart-lambda \
  --query "Stacks[0].Outputs[?OutputKey=='ForecastingFunctionArn'].OutputValue" --output text)

echo "== 7/9 API Gateway =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-apigateway \
  --template-file cloudformation/07-apigateway.yaml \
  --parameter-overrides PredictionFunctionArn="$PRED_ARN" ForecastingFunctionArn="$FORE_ARN"

echo "== 8/9 SNS =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-sns \
  --template-file cloudformation/08-sns.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" NotificationEmail="$EMAIL"

echo ">> Build & push image Docker sebelum deploy ECS."
bash scripts/build_and_push_ecr.sh "$PROVINCE" "$NAME"

VPC_ID=$(aws cloudformation describe-stacks --region "$REGION" --stack-name techmart-networking \
  --query "Stacks[0].Outputs[?OutputKey=='VpcId'].OutputValue" --output text)
SUBNET_A=$(aws cloudformation describe-stacks --region "$REGION" --stack-name techmart-networking \
  --query "Stacks[0].Outputs[?OutputKey=='PublicSubnetAId'].OutputValue" --output text)
SUBNET_B=$(aws cloudformation describe-stacks --region "$REGION" --stack-name techmart-networking \
  --query "Stacks[0].Outputs[?OutputKey=='PublicSubnetBId'].OutputValue" --output text)
SG_LB=$(aws cloudformation describe-stacks --region "$REGION" --stack-name techmart-networking \
  --query "Stacks[0].Outputs[?OutputKey=='SgLoadBalancerId'].OutputValue" --output text)
SG_APPS=$(aws cloudformation describe-stacks --region "$REGION" --stack-name techmart-networking \
  --query "Stacks[0].Outputs[?OutputKey=='SgAppsId'].OutputValue" --output text)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/techmart-ecr-${PROVINCE}-${NAME}:latest"

echo "== 9/9 ECS + ALB + CodeDeploy =="
aws cloudformation deploy --region "$REGION" \
  --stack-name techmart-ecs \
  --template-file cloudformation/09-ecs-alb-codedeploy.yaml \
  --parameter-overrides ProvinceName="$PROVINCE" StudentName="$NAME" \
    VpcId="$VPC_ID" PublicSubnetAId="$SUBNET_A" PublicSubnetBId="$SUBNET_B" \
    SgLoadBalancerId="$SG_LB" SgAppsId="$SG_APPS" ContainerImage="$IMAGE_URI" \
  --capabilities CAPABILITY_NAMED_IAM

echo "Semua stack berhasil dideploy."
