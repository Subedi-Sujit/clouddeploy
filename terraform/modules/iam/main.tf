################################################################
# IAM Module
# Creates two roles required by ECS Fargate:
#
# 1. Task Execution Role - used by ECS itself to pull images
#    from ECR and write logs to CloudWatch.
# 2. Task Role - assumed by the application code at runtime.
#    Used to access AWS services like Secrets Manager.
#
# This separation follows least-privilege: the app code can
# only do what the task role allows.
################################################################

# ----------------------------------------------------------------
# ECS Task Execution Role
# Used by the ECS agent, not by the application.
# ----------------------------------------------------------------
data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.project_name}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = var.tags
}

# Attach the AWS-managed policy for ECS task execution
# (allows pulling ECR images and writing to CloudWatch logs)
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional permission: read secrets from Secrets Manager
# so ECS can inject them as environment variables at task startup.
data "aws_iam_policy_document" "ecs_task_execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name   = "${var.project_name}-ecs-task-execution-secrets"
  role   = aws_iam_role.ecs_task_execution.id
  policy = data.aws_iam_policy_document.ecs_task_execution_secrets.json
}

# ----------------------------------------------------------------
# ECS Task Role
# Assumed by the application code at runtime.
# Currently has no permissions - add only what the app needs.
# ----------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = var.tags
}
