
resource "aws_cloudwatch_event_rule" "backup_restore_status" {
  name          = var.event_name
  description   = var.description
  event_pattern = var.event_pattern
}

resource "aws_cloudwatch_event_target" "tag_replicator_lambda_target" {
  arn  = var.arn
  rule = aws_cloudwatch_event_rule.backup_restore_status.name
}






