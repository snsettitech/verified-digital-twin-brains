# GitHub Repository Configuration with Terraform
# Infrastructure as Code approach to manage settings

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "github" {
  owner = var.github_owner
  token = var.github_token
}

# Variables
variable "github_owner" {
  description = "GitHub organization or user"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "github_token" {
  description = "GitHub API token (use env var GITHUB_TOKEN instead)"
  type        = string
  sensitive   = true
}

variable "main_branch" {
  description = "Main branch to protect"
  type        = string
  default     = "main"
}

variable "enable_security_features" {
  description = "Enable Dependabot and secret scanning"
  type        = bool
  default     = true
}

# Data source to get repo
data "github_repository" "this" {
  full_name = "${var.github_owner}/${var.github_repo}"
}

# Branch protection rule
resource "github_branch_protection" "main" {
  repository_id = data.github_repository.this.node_id
  pattern       = var.main_branch
  
  # Require pull request
  required_pull_request_reviews {
    dismiss_stale_reviews           = true
    require_code_owner_reviews      = true
    required_approving_review_count = 1
    require_last_push_approval      = false
  }
  
  # Require status checks
  required_status_checks {
    strict   = true
    contexts = [
      "code-quality",
      "security-audit",
      "architecture-check",
      "test-coverage",
      "validation",
      "migration-check",
      "config-validation"
    ]
  }
  
  # Enforce rules
  enforce_admins           = false
  allow_force_pushes       = false
  allow_deletions          = false
  require_conversation_resolution = true
}

# Repository settings
resource "github_repository_settings" "this" {
  repository = data.github_repository.this.name
  
  # Pull request settings
  allow_auto_merge  = true
  delete_branch_on_merge = true
  allow_merge_commit = true
  allow_squash_merge = true
  allow_rebase_merge = true
  
  # Security
  has_issues = true
  has_wiki   = false
  has_projects = true
  
  # Default branch
  default_branch = var.main_branch
}

# Optional: Enable Dependabot
resource "github_repository_dependabot_security_updates" "this" {
  count      = var.enable_security_features ? 1 : 0
  repository = data.github_repository.this.name
  enabled    = true
}

# Optional: Enable secret scanning (requires push protection addon)
resource "github_repository_secret_scanning" "this" {
  count      = var.enable_security_features ? 1 : 0
  repository = data.github_repository.this.name
  enabled    = true
}

# Optional: Push protection
resource "github_repository_secret_scanning_push_protection" "this" {
  count      = var.enable_security_features ? 1 : 0
  repository = data.github_repository.this.name
  enabled    = true
}

# Outputs
output "repository_name" {
  value       = data.github_repository.this.name
  description = "Repository name"
}

output "branch_protected" {
  value       = github_branch_protection.main.pattern
  description = "Protected branch"
}

output "protection_rules" {
  value = {
    required_approvals           = 1
    dismiss_stale_reviews        = true
    require_code_owner_reviews   = true
    required_status_checks_count = 7
    enforce_for_admins          = false
    allow_force_pushes          = false
    allow_deletions             = false
  }
  description = "Applied protection rules"
}
