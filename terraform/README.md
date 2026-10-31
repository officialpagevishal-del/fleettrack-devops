# Terraform / AWS rollout plan

Provision in this order after the local app works:
1. AWS account + MFA + budget alert; use a dedicated deployment role and least privilege.
2. VPC with public subnets only for load balancer, private subnets for EKS nodes and RDS.
3. ECR repository for API images.
4. RDS PostgreSQL with encryption, private accessibility, backups and security-group access only from application workloads.
5. EKS with managed node group, OIDC/IRSA and cluster logging.
6. AWS Load Balancer Controller + TLS certificate + DNS.
7. Secrets Manager / External Secrets, CloudWatch and Prometheus/Grafana.

Do not run `terraform apply` until the configuration is reviewed. Add remote state in an encrypted S3 bucket with locking, pin provider versions, define budgets, and never hard-code credentials. This starter intentionally leaves account-specific networking and IAM values unconfigured rather than providing unsafe defaults.
