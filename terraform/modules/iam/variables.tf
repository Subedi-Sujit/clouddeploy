variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "secret_arns" {
  description = "ARNs of secrets the task execution role can read"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}
