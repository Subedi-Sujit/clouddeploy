################################################################
# Secrets Module
# Stores sensitive values in AWS Secrets Manager.
# ECS injects these into container environment variables at runtime.
#
# IMPORTANT: Never commit real passwords. The password value
# here would be provided via TF_VAR or generated dynamically.
################################################################

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.project_name}/db-password"
  description             = "PostgreSQL password for ${var.project_name}"
  recovery_window_in_days = 0 # Set to 7+ in production
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}
