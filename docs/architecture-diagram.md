# Architecture Diagram

Draw this in [Excalidraw](https://excalidraw.com) (free, no signup required) and export as PNG to `docs/architecture.png`.

## What to draw

```
                                Internet
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Application Load Balancer    │
                    │   (Public Subnets, AZ-a & AZ-b)│
                    └───────────────┬───────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                                       ▼
        ┌──────────────┐                       ┌──────────────┐
        │ ECS Task     │                       │ ECS Task     │
        │ (Fargate)    │                       │ (Fargate)    │
        │ Private AZ-a │                       │ Private AZ-b │
        │ Flask:5000   │                       │ Flask:5000   │
        └──────┬───────┘                       └──────┬───────┘
               │                                       │
               └──────────────┬────────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │   RDS Postgres   │
                    │   (Multi-AZ)     │
                    │   Private        │
                    └──────────────────┘

        Side components:
        ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
        │ ECR             │  │ Secrets Manager │  │ CloudWatch      │
        │ (image registry)│  │ (DB password)   │  │ (logs, alarms)  │
        └─────────────────┘  └─────────────────┘  └─────────────────┘

        Outbound traffic from private subnets → NAT Gateway → Internet
```

## Elements to include

1. **VPC boundary** (big rectangle, label "VPC 10.0.0.0/16")
2. **Two public subnets** (one per AZ) containing the ALB and NAT Gateway
3. **Two private subnets** (one per AZ) containing ECS tasks and RDS
4. **Internet Gateway** at the top
5. **NAT Gateway** in one public subnet, with arrows showing private→public flow
6. **External services**: ECR, Secrets Manager, CloudWatch (off to the side)
7. **Traffic arrows**:
   - User → IGW → ALB (port 80)
   - ALB → ECS tasks (port 5000)
   - ECS tasks → RDS (port 5432)
   - ECS tasks → Secrets Manager (at startup)
   - ECS tasks → CloudWatch Logs

## Color suggestions

- Public subnets: light blue
- Private subnets: light gray
- ECS tasks: orange
- Database: dark blue
- External AWS services: yellow

Keep it simple. Recruiters look at this for 10 seconds. Clarity beats prettiness.
