variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ca-central-1"
}

variable "project_name" {
  description = "Name used to prefix all resources"
  type        = string
  default     = "clouddeploy"
}

variable "availability_zones" {
  description = "AZs to use"
  type        = list(string)
  default     = ["ca-central-1a", "ca-central-1b"]
}

variable "db_password" {
  description = "Database password (set via TF_VAR_db_password env var)"
  type        = string
  sensitive   = true
}
