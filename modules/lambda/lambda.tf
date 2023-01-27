
#Lambda assume role
resource "aws_iam_role" "iam_role_lambda_tag_replicator" {
  name = "lambda-backup-tag-replicator"

  assume_role_policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [
      {
        "Action" : "sts:AssumeRole",
        "Principal" : {
          "Service" : "lambda.amazonaws.com"
        },
        "Effect" : "Allow",
        "Sid" : ""
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "lambda_aws_backup_role_policy" {
  role       = aws_iam_role.iam_role_lambda_tag_replicator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "lambda_restore_backup_role_policy" {
  role       = aws_iam_role.iam_role_lambda_tag_replicator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

resource "aws_iam_role_policy_attachment" "lambda_backup_operator_role_policy" {
  role       = aws_iam_role.iam_role_lambda_tag_replicator.name
  policy_arn = "arn:aws:iam::aws:policy/AWSBackupOperatorAccess"
}


resource "aws_iam_policy" "lambda_replicator_policy" {
  name = "lambda-tags-replicator-policy"

  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [
      {
        "Sid" : "Stmt1656081837783",
        "Effect" : "Allow",
        "Action" : [
          "ec2:Describe*",
          "ec2:CreateTags",
          "ec2:DescribeTags"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "Stmt1656082220786",
        "Action" : [
          "rds:AddTagsToResource",
          "rds:ListTagsForResource"
        ],
        "Effect" : "Allow",
        "Resource" : "*"
      },
      {
        "Action" : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Effect" : "Allow",
        "Resource" : "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "test-attach" {
  role       = aws_iam_role.iam_role_lambda_tag_replicator.name
  policy_arn = aws_iam_policy.lambda_replicator_policy.arn
}


data "archive_file" "my_lambda_read_function" {
  source_file = "${path.module}/lambda_handler.py"
  output_path = "${path.module}/files/lambda.zip"
  type        = "zip"
}

#Lambda function
resource "aws_lambda_function" "lambda_replicator" {
  filename         = "${path.module}/files/lambda.zip"
  source_code_hash = data.archive_file.my_lambda_read_function.output_base64sha256
  function_name    = var.function_name
  role             = aws_iam_role.iam_role_lambda_tag_replicator.arn
  handler          = "lambda_handler.handler"
  runtime          = "python3.7"
  memory_size      = "1024"
  timeout          = 6
}




