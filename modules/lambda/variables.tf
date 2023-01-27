variable "source_arn" {
  type        = string
  default     = ""
  description = "The Amazon Resource Name (ARN) associated with the role that is used for target invocation."
}

variable "function_name" {
  type        = string
  default     = ""
  description = "the name of the lambda function triggered by the rule"
}
