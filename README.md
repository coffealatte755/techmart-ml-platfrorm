# TechMart ML — Cloud-Native Product Recommendation System (AWS)

Implementasi referensi untuk studi kasus **LKS Cloud Computing** berupa sistem rekomendasi produk e-commerce yang **cloud-native, serverless, dan event-driven** di atas **AWS Region us-east-1 (N. Virginia)**.

> **Catatan**
>
> Ganti seluruh placeholder berikut sebelum deployment:
>
> * `<province>`
> * `<name>`
>
> Format penamaan resource:
>
> ```text
> techmart-<service>-<province>-<name>
> ```
>
> Lakukan perubahan pada seluruh file parameter, CloudFormation, dan `.env`.

---

# Struktur Proyek

```text
techmart-ml-platform/
├── cloudformation/                      # Infrastructure as Code (1 file = 1 layanan)
│   ├── 00-parameters.yaml.sample        # Parameter deployment
│   ├── 01-networking.yaml               # VPC, Subnet, Route Table, NAT Instance, Security Group
│   ├── 02-s3.yaml                       # S3 Data Lake + Bucket Policy + Lifecycle
│   ├── 03-dynamodb.yaml                 # Tabel DynamoDB
│   ├── 04-glue.yaml                     # Glue Database, Crawler, ETL Job
│   ├── 05-sagemaker.yaml                # SageMaker Notebook Instance
│   ├── 06-lambda.yaml                   # Lambda Functions + Log Tables
│   ├── 07-apigateway.yaml               # API Gateway, API Key, Usage Plan
│   ├── 08-sns.yaml                      # SNS Topic + Email Subscription
│   └── 09-ecs-alb-codedeploy.yaml       # ECS Fargate, ALB, ECR, CodeDeploy
│
├── dataset-generation/
│   └── generate_datasets.py             # Generator dataset sintetis
│
├── glue-etl/
│   └── techmart_etl_job.py              # AWS Glue PySpark ETL
│
├── sagemaker/
│   └── train_recommendation_model.ipynb # Training model rekomendasi
│
├── lambda/
│   ├── prediction/
│   │   └── lambda_function.py
│   └── forecasting/
│       └── lambda_function.py
│
├── app/                                 # Flask Application (ECS)
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── codedeploy/
│   ├── appspec.yml
│   └── taskdef.json
│
├── scripts/
│   ├── deploy_all.sh                    # Deploy seluruh CloudFormation
│   ├── package_lambda.sh                # Package & upload Lambda
│   └── build_and_push_ecr.sh            # Build & push Docker image ke ECR
│
└── docs/
    └── architecture.md                  # Dokumentasi arsitektur dan deployment
```

---

# Urutan Pengerjaan

Ikuti tahapan berikut agar dependency antar layanan terpenuhi.

| No | Tahapan                                  | File                                         |
| -- | ---------------------------------------- | -------------------------------------------- |
| 1  | Deploy Networking                        | `cloudformation/01-networking.yaml`          |
| 2  | Deploy S3 Data Lake                      | `cloudformation/02-s3.yaml`                  |
| 3  | Generate dataset & upload ke `raw-data/` | `dataset-generation/generate_datasets.py`    |
| 4  | Deploy AWS Glue                          | `cloudformation/04-glue.yaml`                |
| 5  | Jalankan Glue ETL Job                    | `glue-etl/techmart_etl_job.py`               |
| 6  | Deploy DynamoDB                          | `cloudformation/03-dynamodb.yaml`            |
| 7  | Deploy SageMaker                         | `cloudformation/05-sagemaker.yaml`           |
| 8  | Training model rekomendasi               | `sagemaker/train_recommendation_model.ipynb` |
| 9  | Package Lambda                           | `scripts/package_lambda.sh`                  |
| 10 | Deploy Lambda                            | `cloudformation/06-lambda.yaml`              |
| 11 | Deploy API Gateway                       | `cloudformation/07-apigateway.yaml`          |
| 12 | Deploy SNS                               | `cloudformation/08-sns.yaml`                 |
| 13 | Build & Push Docker Image ke ECR         | `scripts/build_and_push_ecr.sh`              |
| 14 | Deploy ECS, ALB, dan CodeDeploy          | `cloudformation/09-ecs-alb-codedeploy.yaml`  |
| 15 | Verifikasi Endpoint API Gateway          | `docs/architecture.md`                       |
| 16 | Monitoring CloudWatch Dashboard & Alarm  | `docs/architecture.md`                       |

---

# Urutan Deploy CloudFormation

```text
01-networking
        │
        ▼
02-s3
        │
        ▼
04-glue
        │
        ▼
03-dynamodb
        │
        ▼
05-sagemaker
        │
        ▼
06-lambda
        │
        ▼
07-apigateway
        │
        ▼
08-sns
        │
        ▼
09-ecs-alb-codedeploy
```

---

# Quick Start

Clone repository.

```bash
git clone <repository-url>
cd techmart-ml-platform
```

Salin file parameter.

```bash
cp cloudformation/00-parameters.yaml.sample cloudformation/00-parameters.yaml
```

Edit parameter berikut:

* `ProvinceName`
* `StudentName`

Kemudian jalankan deployment.

```bash
bash scripts/deploy_all.sh
```

---

# Konvensi Penamaan Resource

Seluruh resource AWS wajib menggunakan prefix berikut.

```text
techmart-
```

Contoh:

```text
techmart-vpc-jabar-ajrina
techmart-datalake-jabar-ajrina
techmart-api-jabar-ajrina
techmart-ecs-jabar-ajrina
techmart-alb-jabar-ajrina
techmart-lambda-prediction-jabar-ajrina
```

---

# Ketentuan IAM

Seluruh layanan **wajib menggunakan IAM Role yang sudah tersedia di AWS Academy**, yaitu **LabRole**.

Jangan membuat IAM Role baru.

Gunakan ARN berikut:

```text
arn:aws:iam::<AccountId>:role/LabRole
```

Role ini digunakan oleh layanan seperti:

* AWS Glue
* AWS Lambda
* Amazon SageMaker
* Amazon ECS Task Execution
* AWS CodeDeploy
* API Gateway (jika diperlukan)

---

# Catatan Penting

* Seluruh infrastruktur dibuat menggunakan **AWS CloudFormation**.
* Dataset **tidak dibuat menggunakan CloudFormation**, tetapi melalui script Python sesuai instruksi soal.
* Seluruh nama resource harus diawali dengan prefix **`techmart-`**.
* Detail parameter deployment, endpoint API, diagram arsitektur, serta monitoring CloudWatch tersedia pada:

  * `docs/architecture.md`
  * komentar di masing-masing template CloudFormation.
