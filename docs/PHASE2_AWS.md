# Phase 2: AWS Validation

Phase 1 runs the full stack locally with no cloud cost. Phase 2 deploys selected components to AWS briefly to capture real screenshots and validate the Terraform code.

## Goal

Prove the Terraform actually provisions working AWS infrastructure, then destroy everything before charges accumulate.

## Cost Plan

| Component        | Status     | Why                                            |
| ---------------- | ---------- | ---------------------------------------------- |
| ECR              | ✅ Deploy   | Free tier: 500 MB storage, fractional cents    |
| IAM roles        | ✅ Deploy   | Always free                                    |
| Secrets Manager  | ✅ Deploy   | ~$0.40/month per secret; delete after demo     |
| ECS Fargate      | ✅ Deploy   | Pay-per-second; run for 1 hour ≈ $0.05         |
| ALB              | ⚠️ Deploy  | ~$0.022/hour; destroy within hours             |
| NAT Gateway      | ❌ Skip    | $32/month — biggest cost trap. Use a public subnet for the task in dev validation, or use VPC endpoints. |
| RDS              | ❌ Skip    | Use the local Postgres for the demo. Show RDS in Terraform only. |

Estimated total Phase 2 cost if you tear down within 4 hours: **under $2**.

## Pre-flight Checklist

1. Create an AWS account; enable MFA on root.
2. Create an IAM user `clouddeploy-deployer` with programmatic access. Attach only the policies needed (avoid `AdministratorAccess` if possible).
3. Configure AWS CLI: `aws configure`.
4. Set a billing alarm at $5 in the Billing console. Don't skip this.

## Setting Up Remote State (one-time)

```bash
# Create the S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket clouddeploy-tf-state-<random-suffix> \
  --region ca-central-1 \
  --create-bucket-configuration LocationConstraint=ca-central-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket clouddeploy-tf-state-<random-suffix> \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name clouddeploy-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ca-central-1
```

Then uncomment the `backend "s3"` block in `terraform/environments/dev/main.tf` and run `terraform init -migrate-state`.

## Deploying

```bash
cd terraform/environments/dev

# Set the database password as an env var (never commit it)
export TF_VAR_db_password="$(openssl rand -base64 24)"

# Initialize
terraform init

# Validate
terraform validate
terraform fmt -check -recursive

# Review the plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

## Pushing the Docker Image to ECR

```bash
# Get the ECR URL Terraform created
ECR_URL=$(terraform output -raw ecr_repository_url)

# Log in
aws ecr get-login-password --region ca-central-1 \
  | docker login --username AWS --password-stdin $(echo $ECR_URL | cut -d/ -f1)

# Build and push
docker build -t clouddeploy:latest .
docker tag clouddeploy:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Force ECS to pick up the new image
aws ecs update-service \
  --cluster clouddeploy-cluster \
  --service clouddeploy-service \
  --force-new-deployment
```

## Capturing Evidence

While deployed, capture screenshots of:

- AWS Console: VPC with public/private subnets shown
- ECS cluster with the running service and tasks
- ECR repository with the pushed image
- Secrets Manager showing the secret (value masked)
- CloudWatch Logs showing application output
- CloudWatch alarms (in OK state)
- `terraform output` showing the ALB URL working with `curl`
- GitHub Actions run showing pipeline success

## Tearing Down (CRITICAL)

```bash
terraform destroy
```

Confirm in the AWS Console that NAT Gateways, ALBs, RDS instances, and EIPs are all gone. **These are the things that cost money when forgotten.**

Manually delete the Secrets Manager secret if it has a recovery window > 0:

```bash
aws secretsmanager delete-secret \
  --secret-id clouddeploy/db-password \
  --force-delete-without-recovery
```

## Reliability Demo (optional but powerful for interviews)

Before the final teardown, do this once and screenshot it:

1. Push a deliberately broken image (e.g., remove gunicorn from the Dockerfile so the container crashes on start).
2. Watch ECS try to start the new task, fail, and roll back to the previous version.
3. See the CloudWatch alarm fire for unhealthy targets.
4. Capture the alarm screenshot.
5. Push the fixed image; watch the service recover.

In an interview: *"I tested failure handling by deploying a broken container. ECS health checks failed, the deployment rolled back to the previous task definition, and the CloudWatch unhealthy-targets alarm fired. Recovery was automatic once I pushed a fixed image."*

That sentence is what separates someone who built a toy from someone who built a system.
