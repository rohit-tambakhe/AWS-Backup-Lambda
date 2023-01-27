output "rule_id" {
  value       = aws_cloudwatch_event_rule.backup_restore_status.id
  description = "The ID of the eventbridge rule"
}

output "rule_arn" {
  value       = aws_cloudwatch_event_rule.backup_restore_status.arn
  description = "The ARN of the eventbridge rule."
}

