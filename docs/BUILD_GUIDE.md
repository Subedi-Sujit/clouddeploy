# Phase 1 Build Guide

This is the day-by-day plan to get Phase 1 running on your Windows + WSL2 + Docker Desktop setup. Read each section before doing it. Don't skip the "Verify" steps.

## Prerequisites

Before you start:

- [ ] Docker Desktop is installed and running (you've used it before — the WSL2 issue should be resolved)
- [ ] VS Code with the Claude Code extension
- [ ] Git installed (`git --version`)
- [ ] Python 3.12 on WSL2 (`python3 --version`)
- [ ] A GitHub account

## Day 1: Project Setup + Flask App (~1.5 hours)

### 1. Create the directory structure

```bash
mkdir clouddeploy && cd clouddeploy
mkdir -p app tests terraform/modules/{networking,ecs,rds,iam,secrets} \
  terraform/environments/dev .github/workflows \
  monitoring/prometheus monitoring/grafana/provisioning/{datasources,dashboards} docs
```

### 2. Create `app/main.py`

Copy the Flask app code. Read it line by line. The important parts to understand:

- The `TESTING` env var switches the app to SQLite for tests
- `db.create_all()` runs at startup to ensure tables exist
- `/health` is unauthenticated and used by load balancers
- `/metrics` is auto-exposed by `prometheus_flask_exporter`

### 3. Create `app/requirements.txt` and `app/requirements-dev.txt`

### 4. Verify the app runs locally (without Docker)

```bash
cd clouddeploy
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements-dev.txt

# Run tests
TESTING=true pytest tests/ -v
```

Expected: 9 tests pass. If anything fails, fix it before moving on.

## Day 2: Docker + Compose (~2 hours)

### 1. Create the `Dockerfile`

Read every line. Understand:

- Why two stages (smaller final image, no build tools)
- Why a non-root user (security)
- Why gunicorn instead of `flask run` (production WSGI server)

### 2. Create `docker-compose.yml`

### 3. Create `.dockerignore`

### 4. Build and run

```bash
docker compose up --build
```

In another terminal:

```bash
# Health check
curl http://localhost:5000/health
# {"status":"healthy"}

# Create a task
curl -X POST http://localhost:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Test task"}'

# List tasks
curl http://localhost:5000/api/tasks

# Check metrics
curl http://localhost:5000/metrics | head -20
```

**Verify:** all curl commands return expected JSON. The `/metrics` endpoint shows Prometheus-format metrics.

### 5. Tear down cleanly

```bash
docker compose down -v   # -v also removes volumes (clean slate)
```

## Day 3: Monitoring (~1.5 hours)

### 1. Create the Prometheus config files

- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/alerts.yml`

### 2. Create the Grafana provisioning files

- `monitoring/grafana/provisioning/datasources/prometheus.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/provisioning/dashboards/clouddeploy-overview.json`

### 3. Start the stack and verify

```bash
docker compose up -d
```

Open in browser:

- http://localhost:9090 — Prometheus UI. Go to Status → Targets. You should see `clouddeploy-app` as UP.
- http://localhost:9090/alerts — should show your 3 alert rules.
- http://localhost:3000 — Grafana (admin / admin). Go to Dashboards. The "CloudDeploy Overview" should be there.

### 4. Generate traffic and watch the dashboard

```bash
# Generate some load
for i in {1..50}; do
  curl -s -X POST http://localhost:5000/api/tasks \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"task $i\"}" > /dev/null
  curl -s http://localhost:5000/api/tasks > /dev/null
  sleep 0.2
done
```

**Verify:** Grafana dashboard shows request rate climbing, latency graphs populating.

### 5. Trigger an alert (optional but cool)

Stop the app: `docker compose stop app`. Wait 1 minute. Go to http://localhost:9090/alerts — the `AppDown` alert should be firing. Restart: `docker compose start app`.

## Day 4: Terraform Modules (~3 hours)

This day is purely about writing code. You won't deploy anything to AWS yet. The goal is for `terraform validate` to pass.

### 1. Install Terraform on WSL2

```bash
sudo apt update && sudo apt install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform
terraform version
```

### 2. Create the module files

For each module (`networking`, `iam`, `secrets`, `rds`, `ecs`) create three files:

- `main.tf` — resources
- `variables.tf` — inputs
- `outputs.tf` — outputs

Take your time. Read each resource. Understand:

- VPC + subnets + route tables = the networking foundation
- Security groups are stateful firewalls; ALB SG accepts from internet, ECS SG accepts only from ALB SG, RDS SG accepts only from ECS SG
- IAM has two roles: execution (for ECS itself) and task (for the app code)
- Secrets Manager stores the password; ECS injects it as an env var at startup

### 3. Create the dev environment

`terraform/environments/dev/main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars.example`.

### 4. Validate

```bash
cd terraform/environments/dev
terraform init -backend=false   # Skip backend init for now
terraform fmt -recursive ..
terraform validate
```

**Verify:** "Success! The configuration is valid."

If you get errors, read them carefully. Common issues:

- Missing variable in a module call
- Typo in a resource reference
- Wrong output name being referenced

### 5. Run tfsec locally

```bash
docker run --rm -v $(pwd)/..:/src aquasec/tfsec /src
```

This will flag some issues (expected, since we have insecure defaults for dev). Read them. Decide which are acceptable trade-offs and document in the README's Design Decisions section.

## Day 5: GitHub Actions (~1 hour)

### 1. Create `.github/workflows/ci.yml`

### 2. Create the `.gitignore`

### 3. Initialize git and push

```bash
cd clouddeploy
git init -b main
git add .
git commit -m "Initial commit: CloudDeploy Phase 1"

# Create a public repo on GitHub called clouddeploy, then:
git remote add origin git@github.com:<your-username>/clouddeploy.git
git push -u origin main
```

### 4. Watch the pipeline run

Go to the Actions tab on GitHub. The CI workflow should trigger automatically. Three jobs: test, security, build.

**Verify:** all three jobs pass (the build job only runs on main). Click into each to read the logs.

### 5. Fix anything that fails

Common issues:

- Test job: a missing dependency. Check `requirements-dev.txt`.
- Security job: tfsec might flag issues — that's expected with `soft_fail: true`.
- Build job: Dockerfile typo or missing file.

## Day 6: Documentation + Diagram (~2 hours)

### 1. Polish the README

The README I gave you is comprehensive. Read through it. Make sure every section is accurate for your repo.

### 2. Draw the architecture diagram in Excalidraw

Go to https://excalidraw.com. Recreate the diagram from `docs/architecture-diagram.md`. Export as PNG. Save to `docs/architecture.png`. Commit and push.

### 3. Record a demo video (2-3 minutes)

Use OBS Studio (free, https://obsproject.com).

Script:

1. Show the GitHub repo. Scroll through README, click on the Actions tab to show CI passing.
2. Open VS Code. Show the repo structure briefly.
3. Run `docker compose up`. Show containers starting.
4. Curl a few endpoints in the terminal — create task, list tasks.
5. Open Prometheus, show targets are UP.
6. Open Grafana, show the dashboard with live metrics.
7. Generate some load with the loop. Show the dashboard updating.
8. (Optional) Stop the app, show the alert firing in Prometheus.

Upload to YouTube (unlisted) or Loom (free). Link it from the README.

## Day 7: Review + Apply (~1 hour)

### 1. Review the whole repo as a recruiter would

Open the GitHub repo in an incognito window. Read it like a stranger. Can you understand what this project does in 60 seconds?

### 2. Update your resume

Add this bullet to the projects section, at the top:

> **CloudDeploy** — Built a production-style containerized web application platform demonstrating Infrastructure as Code (modular Terraform for AWS VPC, ECS Fargate, RDS, IAM, Secrets Manager), CI/CD automation (GitHub Actions with Trivy and tfsec security scanning), and observability (Prometheus + Grafana with SLO-based alerting). Designed for multi-AZ high availability with least-privilege IAM. [GitHub link]

### 3. Start applying

You now have a portfolio piece that demonstrates exactly the skills cloud and DevOps roles list. Apply to 10 roles this week. Mention the project in cover letters.

## When You Get Stuck

- Each technology has excellent docs: Flask, Docker, Terraform AWS provider, Prometheus, Grafana.
- If a tool's behavior surprises you, *read the error message slowly*. Most Terraform errors tell you exactly which file and line.
- If you're stuck for more than 30 minutes on one thing, come back to me. Tell me the exact error message and what you've tried.
