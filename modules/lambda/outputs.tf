output "arn" {
  value       = aws_lambda_function.lambda_replicator.arn
  description = "The ARN of the eventbridge rule."
}

output "function_name" {
  value       = aws_lambda_function.lambda_replicator.function_name
  description = "The ARN of the eventbridge rule."
}