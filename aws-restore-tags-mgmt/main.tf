
provider "aws" {
  region = "us-east-1"
}

variable "event_name" {
  type        = string
  description = "Name of the Backup Event"
  default     = "aws-backup-restore-completed"
}

variable "event_pattern" {
  type        = string
  description = "Pattern of the restore event completed"
  default     = <<PATTERN
{
  "source": [
    "aws.backup"
  ],
  "detail-type": [
    "Restore Job State Change"
  ],
  "detail": {
		"status": ["COMPLETED"]
	}
}
PATTERN
}


module "operation_support_account_lambda" {
  source        = "../modules/lambda"
  function_name = "lambda_replicate_tags"

}

module "operation_support_account_eventbridge_event" {
  source        = "../modules/eventbridge-restore-job"
  event_name    = var.event_name
  description   = "EventBridge rule to match AWS Backup events to trigger tag replicator Lambda function."
  event_pattern = var.event_pattern
  arn           = module.operation_support_account_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_lambda" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = module.operation_support_account_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = module.operation_support_account_eventbridge_event.rule_arn
}






