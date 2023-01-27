variable "event_name" {
  type        = string
  default     = ""
  description = "Name of the event."
}

variable "description" {
  type        = string
  default     = ""
  description = "The description for the rule."
}

variable "event_pattern" {
  default     = null
  description = "Event pattern described by a JSON object."
}

variable "arn" {
  type        = string
  default     = ""
  description = "The Amazon Resource Name (ARN) associated with the role that is used for target invocation."
}







