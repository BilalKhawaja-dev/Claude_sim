locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

# ------------------------------------------------------------------------------
# SES Email Identity Verification
# ------------------------------------------------------------------------------

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}
