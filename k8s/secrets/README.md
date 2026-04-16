# Kubernetes Secrets

This directory contains **template** Secret manifests for the Claude Simulator platform. These files use placeholder values and must be populated with real credentials before applying.

## Required Secrets

| Secret | Namespace | Purpose |
|--------|-----------|---------|
| `rds-credentials` | `claude-simulator` | PostgreSQL RDS connection details for the backend |
| `keycloak-admin-secret` | `auth` | Keycloak admin console password |
| `keycloak-db-secret` | `auth` | Keycloak's RDS database password |
| `ses-config` | `auth` | AWS SES email configuration |

## Usage

1. Copy each template and replace placeholder values with real credentials.
2. Apply with `kubectl`:

```bash
kubectl create namespace claude-simulator
kubectl create namespace auth

kubectl apply -f k8s/secrets/rds-credentials.yaml
kubectl apply -f k8s/secrets/keycloak-admin-secret.yaml
kubectl apply -f k8s/secrets/keycloak-db-secret.yaml
kubectl apply -f k8s/secrets/ses-config.yaml
```

Alternatively, create secrets directly without manifest files:

```bash
kubectl create secret generic rds-credentials \
  -n claude-simulator \
  --from-literal=host=<RDS_ENDPOINT> \
  --from-literal=port=5432 \
  --from-literal=database=claude_simulator \
  --from-literal=username=<DB_USER> \
  --from-literal=password=<DB_PASSWORD>
```

## IMPORTANT: Do Not Commit Real Credentials

Actual secret values must **never** be committed to source control. Add the following to your `.gitignore`:

```
# Prevent committing populated secret manifests
k8s/secrets/*-populated.yaml
```

The template files in this directory use placeholder values only and are safe to commit.

## Production Recommendation

For production deployments, use one of:

- **AWS Secrets Manager** + **External Secrets Operator**: Syncs AWS Secrets Manager entries into K8s Secrets automatically. Install via Helm and create `ExternalSecret` resources pointing to your AWS secrets.
- **AWS Systems Manager Parameter Store**: Lower cost alternative for non-rotating secrets.
- **Sealed Secrets**: Encrypt secrets in-repo using Bitnami Sealed Secrets controller.

These approaches avoid storing any secret values in manifests or CI/CD variables.
