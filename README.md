# TechMart ML — Cloud-Native Product Recommendation System (AWS)

Implementasi referensi untuk studi kasus LKS Cloud Computing:
sistem rekomendasi produk e-commerce yang *cloud-native*, *serverless*,
dan *event-driven* di atas AWS (region **us-east-1 / N. Virginia**).

> Ganti semua placeholder `<province>` dan `<name>` sesuai instruksi soal
> (`techmart-<service>-<province>-<name>`) di setiap file parameter/`.env`.

## Struktur Folder

```
techmart-ml-platform/
├── cloudformation/          # Seluruh infrastruktur (IaC), 1 file = 1 layanan
│   ├── 00-parameters.yaml.sample
│   ├── 01-networking.yaml       # VPC, subnet, route table, NAT instance, SG
│   ├── 02-s3.yaml                # Data lake bucket + policy + lifecycle
│   ├── 03-dynamodb.yaml          # 3 tabel DynamoDB
│   ├── 04-glue.yaml              # Database, Crawler, ETL Job
│   ├── 05-sagemaker.yaml         # Notebook instance
│   ├── 06-lambda.yaml            # 2 fungsi Lambda + DynamoDB log tables
│   ├── 07-apigateway.yaml        # REST API + API Key + Usage Plan
│   ├── 08-sns.yaml               # Topic + email subscription
│   └── 09-ecs-alb-codedeploy.yaml# ECR, ECS Fargate, ALB blue/green, CodeDeploy
├── dataset-generation/
│   └── generate_datasets.py      # Generator 4 dataset sintetis
├── glue-etl/
│   └── techmart_etl_job.py       # PySpark job untuk AWS Glue
├── sagemaker/
│   └── train_recommendation_model.ipynb
├── lambda/
│   ├── prediction/lambda_function.py
│   └── forecasting/lambda_function.py
├── app/                           # Aplikasi container (Flask) untuk ECS
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── codedeploy/
│   ├── appspec.yml
│   └── taskdef.json
├── scripts/
│   ├── deploy_all.sh              # Orkestrasi deploy CloudFormation berurutan
│   ├── package_lambda.sh          # Zip kode Lambda & upload ke S3
│   └── build_and_push_ecr.sh      # Build & push image Docker ke ECR
└── docs/
    └── architecture.md
```

## Urutan Pengerjaan (mengikuti urutan soal)

1. `cloudformation/01-networking.yaml` — VPC/Subnet/NAT/SG
2. `cloudformation/02-s3.yaml` — Data Lake
3. `dataset-generation/generate_datasets.py` — generate & upload dataset ke `raw-data/`
4. `cloudformation/04-glue.yaml` + `glue-etl/techmart_etl_job.py`
5. `cloudformation/03-dynamodb.yaml`
6. `cloudformation/05-sagemaker.yaml` + `sagemaker/train_recommendation_model.ipynb`
7. `scripts/package_lambda.sh` lalu `cloudformation/06-lambda.yaml`
8. `cloudformation/07-apigateway.yaml`
9. `cloudformation/08-sns.yaml`
10. `scripts/build_and_push_ecr.sh` lalu `cloudformation/09-ecs-alb-codedeploy.yaml`
11. Verifikasi endpoint API Gateway (lihat `docs/architecture.md`)
12. CloudWatch (dashboard/alarm) — lihat catatan di `docs/architecture.md`

Detail tiap langkah, urutan `aws cloudformation deploy`, dan parameter
lengkap ada di `docs/architecture.md` dan komentar di masing-masing file.

## Cara pakai cepat

```bash
git clone <repo-anda>
cd techmart-ml-platform
cp cloudformation/00-parameters.yaml.sample cloudformation/00-parameters.yaml
# edit ProvinceName & StudentName
bash scripts/deploy_all.sh
```

## Catatan Penting

- Semua resource IAM Role **wajib** memakai role `LabRole` yang sudah ada
  di akun AWS Academy (bukan dibuat baru) — direferensikan via
  `arn:aws:iam::<AccountId>:role/LabRole`.
- Semua service dibuat lewat CloudFormation **kecuali** dataset (dibuat
  dengan Python, sesuai instruksi soal).
- Semua nama resource diawali `techmart-`.
