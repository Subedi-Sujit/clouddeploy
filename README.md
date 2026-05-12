# CloudDeploy

A production-style containerized web application platform demonstrating cloud-native infrastructure, DevOps automation, and observability practices.

> **Status:** Phase 1 complete — fully working local environment. Phase 2 (AWS validation) is documented in [docs/PHASE2_AWS.md](docs/PHASE2_AWS.md).

---

## What This Project Is

CloudDeploy is a small Task Manager REST API used as a vehicle to demonstrate the engineering practices that matter for cloud and DevOps roles:

- **Infrastructure as Code** — every AWS resource defined in modular Terraform.
- **Containerization** — multi-stage Docker build, non-root user, healthchecks.
- **CI/CD automation** — GitHub Actions runs lint, tests, security scans, and builds on every push.
- **DevSecOps** — Trivy scans container images, tfsec scans Terraform.
- **Observability** — Prometheus scrapes the app, Grafana visualizes metrics, alert rules defined.
- **Secrets management** — database credentials injected from AWS Secrets Manager at runtime.
- **Least-privilege IAM** — separate execution and task roles.
- **High availability** — multi-AZ design across two availability zones.

The application itself (a CRUD API for tasks) is intentionally simple. The interesting part is *how it is deployed and operated*.

---

## Architecture

![Architecture diagram](docs/architecture.png)

**Traffic flow (AWS deployment):**

1. User hits the Application Load Balancer in public subnets.
2. ALB forwards traffic to Flask containers running on ECS Fargate in private subnets across two AZs.
3. Containers read/write to RDS PostgreSQL (also in private subnets).
4. Database credentials come from AWS Secrets Manager, injected at container start.
5. Logs stream to CloudWatch. CloudWatch alarms watch CPU and target health.
6. The app exposes `/metrics` for Prometheus (used in the local stack).

**Local development** uses Docker Compose to run the same Flask container alongside PostgreSQL, Prometheus, and Grafana.

---

## Tech Stack

| Layer            | Tool                                                            |
| ---------------- | --------------------------------------------------------------- |
| Application      | Python 3.12, Flask, Flask-SQLAlchemy, gunicorn                  |
| Database         | PostgreSQL 16                                                   |
| Container        | Docker (multi-stage build)                                      |
| Local orchestration | Docker Compose                                               |
| IaC              | Terraform (modular: networking, ecs, rds, iam, secrets)         |
| Cloud (target)   | AWS — VPC, ECS Fargate, ALB, RDS, ECR, Secrets Manager, CloudWatch, IAM |
| CI/CD            | GitHub Actions                                                  |
| Security         | Trivy (image scanning), tfsec (IaC scanning)                    |
| Monitoring       | Prometheus + Grafana with alert rules                           |
| Testing          | pytest with SQLite in-memory                                    |

---

## Quick Start (Local)

**Requirements:** Docker Desktop, Git.

```bash
# Clone and enter the repo
git clone <your-fork-url>
cd clouddeploy

# Start the full stack
docker compose up --build

# In another terminal, exercise the API
curl http://localhost:5000/health
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Learn Terraform","description":"Build CloudDeploy"}'
curl http://localhost:5000/api/tasks
```

**What's now running:**

| Service     | URL                          | Credentials      |
| ----------- | ---------------------------- | ---------------- |
| Flask app   | http://localhost:5000        | —                |
| Prometheus  | http://localhost:9090        | —                |
| Grafana     | http://localhost:3000        | admin / admin    |
| PostgreSQL  | localhost:5432               | clouddeploy / devpassword |

Open Grafana → the **CloudDeploy Overview** dashboard auto-loads with request rate, latency percentiles, and error rate panels.

---

## Running Tests

```bash
# Install dev dependencies
pip install -r app/requirements-dev.txt

# Run tests
TESTING=true pytest tests/ -v
```

Tests use SQLite in-memory, so no database setup needed.

---

## API Reference

| Method | Endpoint              | Description           |
| ------ | --------------------- | --------------------- |
| GET    | `/health`             | Liveness probe        |
| GET    | `/ready`              | Readiness probe (checks DB) |
| GET    | `/metrics`            | Prometheus metrics    |
| GET    | `/api/tasks`          | List all tasks        |
| POST   | `/api/tasks`          | Create a task         |
| GET    | `/api/tasks/<id>`     | Get one task          |
| PUT    | `/api/tasks/<id>`     | Update a task         |
| DELETE | `/api/tasks/<id>`     | Delete a task         |

---

## Design Decisions

This section captures the *why* behind the architecture. These are the questions an interviewer will ask.

### Why ECS Fargate instead of EKS or EC2?

Fargate is the right choice for a service of this size:

- **No node management.** EC2 and EKS both require maintaining the underlying compute. Fargate is serverless — AWS handles the host OS.
- **Cost at this scale.** For a small service with predictable load, Fargate is cheaper than running a dedicated EKS control plane (~$73/month before workloads).
- **Operational simplicity.** EKS is the right answer at scale, with multiple teams, or when Kubernetes-specific features are needed. For a 2-task service with a single deployment pipeline, Fargate ships value faster.

### Why private subnets for ECS tasks and RDS?

Defense in depth. The application has no business being directly reachable from the internet — the ALB is the only public-facing component. Tasks reach the internet (for package downloads, AWS API calls) through a NAT Gateway. RDS is similarly isolated; only the ECS task security group can reach it on port 5432.

### Why a single NAT Gateway in dev?

A NAT Gateway costs roughly $32/month per AZ. Production deployments use one per AZ for HA, but in dev a single NAT in one AZ is acceptable and cuts cost in half. The trade-off is documented and reversible.

### Why store the DB password in Secrets Manager, not as a plain env var?

- **Audit trail.** Secrets Manager logs every access in CloudTrail.
- **Rotation.** Secrets Manager can rotate the password automatically and update RDS in lockstep.
- **No secrets in Terraform state or task definitions.** The task definition references the secret ARN; the value is fetched at container start.
- **Cost-conscious alternative:** SSM Parameter Store (free for standard parameters) is a reasonable substitute when rotation isn't needed.

### Why separate task execution role and task role?

- The **task execution role** is used by ECS itself to pull images and write logs. The application code does not assume it.
- The **task role** is assumed by the application code at runtime. Anything the app needs to do in AWS (e.g., publishing to SNS, reading from S3) goes here.

This split means a compromised application container can only do what its task role allows, not what ECS itself can do.

### Why Prometheus + Grafana instead of just CloudWatch?

In the AWS-deployed version, CloudWatch is used for infrastructure metrics (CPU, target health, log aggregation). Prometheus + Grafana add application-level observability — request rates by endpoint, latency percentiles, and custom business metrics — using the same toolchain Platform Engineer and SRE teams use in production. Running them locally proves the integration without paying for managed Prometheus.

### Why multi-stage Docker build?

- The builder stage contains gcc, libpq-dev, and pip caches needed to compile psycopg2.
- The runtime stage contains only the resulting venv and libpq5.
- Result: smaller image (~150 MB vs ~400 MB), smaller attack surface, faster pulls.

### Why a non-root user inside the container?

If an attacker compromises the application and escapes to the container, running as a non-root user limits what they can do inside the container. It's a cheap, standard hardening practice that compliance frameworks like CIS expect.

### Why pin all dependencies?

Reproducible builds. An unpinned `Flask` could pull a new major version with breaking changes the next time the image is rebuilt. Pinning means today's build behaves the same as next month's build.

---

## Repository Layout

```
clouddeploy/
├── app/                          # Flask application
│   ├── main.py                   # Routes, model, app setup
│   ├── requirements.txt          # Production deps
│   └── requirements-dev.txt      # Test deps
├── tests/                        # pytest unit tests
├── Dockerfile                    # Multi-stage build
├── docker-compose.yml            # Local stack
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml        # Scrape config
│   │   └── alerts.yml            # Alert rules
│   └── grafana/
│       └── provisioning/         # Auto-loaded datasources & dashboards
├── terraform/
│   ├── modules/
│   │   ├── networking/           # VPC, subnets, NAT, route tables
│   │   ├── iam/                  # ECS task roles
│   │   ├── secrets/              # Secrets Manager
│   │   ├── ecs/                  # ECR, ALB, cluster, service, alarms
│   │   └── rds/                  # PostgreSQL
│   └── environments/
│       └── dev/                  # Dev environment composition
├── .github/workflows/ci.yml      # GitHub Actions pipeline
└── docs/
    ├── architecture.png          # Architecture diagram
    └── PHASE2_AWS.md             # Steps to deploy to AWS
```

---

## What's Next (Phase 2)

The Terraform code is written for real AWS. Phase 2 deploys selected components to a free-tier AWS account for screenshots and an end-to-end demo, with strict tear-down to avoid cost. See [docs/PHASE2_AWS.md](docs/PHASE2_AWS.md).

---

## License

MIT
