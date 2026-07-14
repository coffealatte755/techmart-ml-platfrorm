# Arsitektur & Panduan Verifikasi — TechMart ML Platform

## Diagram Alur Data

```
[generate_datasets.py] --> S3 raw-data/
                                 |
                          Glue Crawler (techmart-crawler)
                                 |
                     Glue Data Catalog (techmart_database)
                                 |
                    Glue ETL Job (techmart-etl-job, PySpark)
                                 |
                          S3 processed-data/
                                 |
                  SageMaker Notebook (train_recommendation_model.ipynb)
                                 |
                +----------------+------------------+
                |                                    |
       S3 models/hybrid_model.pkl        DynamoDB ProductEmbeddings
                |
   +------------+-------------+
   |                          |
Lambda techmart-ml-prediction   Lambda techmart-ml-forecasting
   |                          |
   +---------- API Gateway (techmart-ml-api) -----------+
                     /predictions   /forecasts
                                 |
                    ECS Fargate (techmart-app) via ALB
                     (blue/green deploy by CodeDeploy)
                                 |
                       DynamoDB UserInteractions /
                       UserRecommendations /
                       MLPredictionResults / MLForecastResults
                                 |
                        SNS (techmart-sns-...) -- alert email
                                 |
                          CloudWatch (logs, alarm, dashboard)
```

## Urutan Deploy CloudFormation

| # | Stack               | Template                                | Bergantung pada     |
|---|----------------------|------------------------------------------|----------------------|
| 1 | techmart-networking  | 01-networking.yaml                       | -                    |
| 2 | techmart-s3          | 02-s3.yaml                               | -                    |
| 3 | techmart-dynamodb    | 03-dynamodb.yaml                         | -                    |
| 4 | techmart-glue        | 04-glue.yaml                             | S3 bucket            |
| 5 | techmart-sagemaker   | 05-sagemaker.yaml                        | -                    |
| 6 | techmart-lambda      | 06-lambda.yaml                           | S3 (model), kode zip |
| 7 | techmart-apigateway  | 07-apigateway.yaml                       | Lambda ARNs          |
| 8 | techmart-sns         | 08-sns.yaml                              | -                    |
| 9 | techmart-ecs         | 09-ecs-alb-codedeploy.yaml               | Networking, ECR image|

Semua ini sudah diorkestrasi oleh `scripts/deploy_all.sh`.

## Verifikasi Layanan

1. **Networking** — cek di Console VPC: 2 subnet publik, 2 subnet privat,
   masing-masing punya alokasi IPv6 /64; route table privat mengarah ke
   instance NAT (bukan NAT Gateway).
2. **S3** — upload file test ke `raw-data/` dari luar (harus bisa `GET`
   tanpa kredensial); coba akses `processed-data/` tanpa role LabRole
   (harus ditolak); cek lifecycle rule pada `models/` di tab *Management*.
3. **Glue** — jalankan crawler, pastikan tabel muncul di
   `techmart_database`; jalankan `techmart-etl-job` dan cek hasil Parquet
   di `processed-data/`.
4. **DynamoDB** — pastikan 3 tabel awal (ProductEmbeddings,
   UserInteractions, UserRecommendations) sudah ada dengan kapasitas
   sesuai spesifikasi (5/5, 10/10, 5/5 RCU/WCU).
5. **SageMaker** — buka notebook, jalankan seluruh sel, pastikan
   `models/hybrid_model.pkl` muncul di S3 dan item baru masuk ke tabel
   `ProductEmbeddings`.
6. **Lambda** — invoke manual:
   ```bash
   aws lambda invoke --function-name techmart-ml-prediction \
     --payload '{"body": "{\"user_id\":\"U0000001\",\"top_n\":5}"}' \
     --cli-binary-format raw-in-base64-out out.json && cat out.json
   ```
7. **API Gateway** — test endpoint dengan API key:
   ```bash
   curl -X POST "$API_URL/predictions" \
     -H "x-api-key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"U0000001","top_n":5}'
   ```
8. **SNS** — konfirmasi email subscription lewat email yang masuk ke
   `handi@seamolec.org`, lalu publish pesan test:
   ```bash
   aws sns publish --topic-arn <TopicArn> --message "Test notifikasi TechMart"
   ```
9. **ECS/ALB/CodeDeploy** — akses `http://<ALB DNS>/health` (harus `200 ok`);
   trigger deployment blue/green baru via CodeDeploy console/CLI dan amati
   traffic shifting dari `techmart-tg-blue` ke `techmart-tg-green`.

## Monitoring & Model Lifecycle Automation (CloudWatch)

Tambahan yang disarankan untuk memenuhi poin "Implement Monitoring and
Model Lifecycle Automation":

- **CloudWatch Alarms**:
  - Lambda `Errors` dan `Duration` (p95) untuk kedua fungsi ML.
  - API Gateway `5XXError` dan `Latency` pada stage `prod`.
  - ECS Service `CPUUtilization`/`MemoryUtilization`.
  - Hubungkan semua alarm ke SNS topic `techmart-sns-<province>-<name>`
    sebagai action, sehingga notifikasi otomatis terkirim ke email.
- **CloudWatch Dashboard** `techmart-dashboard` — gabungkan widget metrik
  Lambda, API Gateway, ECS, dan DynamoDB throttling dalam satu tampilan.
- **Model retraining otomatis**: buat **EventBridge Scheduled Rule**
  (mis. mingguan) yang men-trigger:
  1. Glue Crawler → Glue ETL Job (via Glue Trigger `WORKFLOW` atau
     Step Functions), lalu
  2. SageMaker Processing/Training Job (bisa memanggil notebook sebagai
     *SageMaker Processing Job* terjadwal, atau gunakan
     *SageMaker Pipelines*) untuk retrain model dan overwrite
     `models/hybrid_model.pkl`.
  3. Publish notifikasi ke SNS setelah retraining selesai/gagal.
- Tambahkan resource-resource ini sebagai file CloudFormation baru
  (`cloudformation/10-monitoring.yaml`) jika juri meminta bukti IaC penuh.

## Tips Kompetisi

- Selalu cek *quota* AWS Academy Lab (VPC, EIP, dsb) sebelum deploy stack
  besar seperti ECS/ALB.
- Gunakan `aws cloudformation deploy` (bukan `create-stack`) supaya idempotent
  saat perlu update berulang selama sesi lomba.
- Simpan seluruh output (`ApiInvokeUrl`, `AlbDnsName`, dll.) di satu file
  catatan agar mudah dipakai ulang untuk testing dan penjurian.
