# Claude Simulator

> Production-grade AI chat platform built from scratch. Next.js frontend, Python FastAPI backend, RAG pipeline with pgvector, deployed on AWS EKS with full IaC, CI/CD, and observability. **351 tests. 65 AWS resources. Zero shortcuts.**

## What This Project Demonstrates

This isn't a tutorial follow-along. It's a complete system designed, built, tested, and deployed end-to-end:

- **AI/ML Engineering** — RAG pipeline with vector embeddings, semantic search, conversation memory
- **Full-Stack Development** — React/Next.js frontend with SSE streaming, Python/FastAPI async backend
- **Cloud Architecture** — VPC, EKS, RDS, ALB, ECR, IAM (IRSA), SES — all provisioned via Terraform
- **DevOps & Platform Engineering** — Helm charts, Ansible playbooks, GitHub Actions CI/CD with OIDC federation
- **Observability** — Prometheus metrics, Grafana dashboards, health checks, liveness/readiness probes
- **Security** — Keycloak OIDC (PKCE), JWT validation middleware, least-privilege IAM, encrypted RDS, private subnets
- **Testing** — 351 tests across backend (Hypothesis property-based) and frontend (fast-check), covering 24 formal correctness properties

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              AWS Cloud                   │
                         │                                         │
   Browser ──HTTPS──▶  [ ALB ]                                    │
                         │  ├── /        → Next.js Frontend        │
                         │  ├── /api/*   → FastAPI Backend         │
                         │  ├── /auth/*  → Keycloak                │
                         │  └── /grafana → Grafana                 │
                         │                                         │
                         │  ┌──────────────────────────────┐      │
                         │  │         EKS Cluster           │      │
                         │  │                               │      │
                         │  │  Frontend ◄──SSE──► Backend   │      │
                         │  │                     │    │    │      │
                         │  │  Keycloak    Prometheus  │    │      │
                         │  │  Grafana     Alertmanager│    │      │
                         │  └──────────────────────────┘    │      │
                         │                │                  │      │
                         │         ┌──────▼──────┐   ┌─────▼────┐ │
                         │         │ RDS Postgres │   │ Bedrock  │ │
                         │         │ + pgvector   │   │ Claude   │ │
                         │         └─────────────┘   │ Titan    │ │
                         │                           └──────────┘ │
                         └─────────────────────────────────────────┘
```

## Key Features

| Feature | Implementation |
|---------|---------------|
| **Streaming Chat** | SSE from Bedrock through FastAPI to React, token-by-token rendering |
| **RAG Memory** | pgvector cosine similarity search across conversations, user memory, and session summaries |
| **Model Selection** | Toggle between Claude Sonnet 4 and Opus mid-conversation |
| **Image Understanding** | Upload PNG/JPEG/GIF/WebP, multimodal Bedrock requests |
| **Image Generation** | Titan Image Generator with inline rendering |
| **Session Lifecycle** | 5-min idle detection → AI summary → email via SES → 30-day archival |
| **User Memory** | Manual facts/preferences stored as embeddings, included in every RAG query |
| **Auth** | Keycloak OIDC with PKCE, JWT validation on every request, silent token refresh |

## Test Coverage

```
Backend:  224 tests (Python/Hypothesis)
Frontend: 127 tests (TypeScript/fast-check)
Total:    351 tests — 24 formal correctness properties
```

Property-based tests validate invariants like:
- Chunked text reassembles to the original (no data loss)
- RAG returns at most 5 results, all with cosine similarity ≥ 0.7
- Conversation deletion cascades to messages and embeddings
- JWT validation rejects expired/invalid tokens with 401
- Email retry follows exponential backoff (1s, 2s, 4s)
- Session summaries persist regardless of email delivery outcome

## Infrastructure (Terraform)

**65 AWS resources** across 8 modules:

| Module | Resources |
|--------|-----------|
| `networking` | VPC, public/private subnets, NAT gateway, security groups |
| `eks` | EKS cluster, managed node group (t3.medium, 2-4 nodes), OIDC provider |
| `rds` | PostgreSQL 16 with pgvector, encrypted at rest, private subnet only |
| `ecr` | Frontend + backend repos, image scanning on push, lifecycle policies |
| `alb` | ALB with path-based routing, self-signed TLS, HTTP→HTTPS redirect |
| `iam` | IRSA roles (Bedrock, SES, ECR), GitHub Actions OIDC role, EKS node role |
| `ses` | Email identity verification |
| `state` | S3 + DynamoDB for remote state locking |

## Kubernetes (Helm + Ansible)

- **4 Helm charts**: backend, frontend, Keycloak (bitnami), kube-prometheus-stack
- **5 Ansible roles**: helm-repos, monitoring, keycloak, application, verify
- **3 namespaces**: `claude-simulator`, `auth`, `monitoring`
- **Grafana dashboards**: Backend API metrics, K8s cluster health, RDS performance

## CI/CD Pipeline

```yaml
Push to main → pytest + jest → Docker build → ECR push → EKS deploy
```
- GitHub Actions with AWS OIDC federation (no stored credentials)
- Parallel test jobs, sequential build/deploy
- Rollout verification with `kubectl rollout status`

## Project Structure

```
├── backend/                 # FastAPI + SQLAlchemy + Bedrock
│   ├── app/api/             # Chat, conversations, memory, images, health
│   ├── app/services/        # Bedrock, RAG, session manager, email
│   ├── app/utils/           # Text chunking, SSE streaming
│   └── tests/               # 224 tests (unit + property-based)
├── frontend/                # Next.js 14 + TypeScript
│   └── src/
│       ├── components/      # ChatThread, Sidebar, ModelSelector, ImageUpload, MemoryEditor
│       ├── hooks/           # useChat (SSE streaming hook)
│       └── lib/             # Keycloak OIDC client (PKCE)
├── terraform/               # 8 modules, 65 resources
├── k8s/                     # Helm charts + Grafana dashboards
├── ansible/                 # 5 roles, deploy playbook
├── .github/workflows/       # CI/CD pipeline
└── docker-compose.yml       # Local development (one command)
```

## Quick Start

```bash
# Local development — everything runs in Docker
docker-compose up

# Run all tests
cd backend && python -m pytest tests/ -v    # 224 tests
cd frontend && npx jest --ci                 # 127 tests
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, fast-check |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Hypothesis |
| Database | PostgreSQL 16 + pgvector |
| AI/ML | AWS Bedrock — Claude Sonnet 4, Opus, Titan Embeddings v2, Titan Image Generator |
| Auth | Keycloak (OIDC PKCE flow) |
| Monitoring | Prometheus, Grafana, node-exporter, kube-state-metrics |
| Infrastructure | Terraform, EKS, RDS, ECR, ALB, SES, IAM (IRSA) |
| CI/CD | GitHub Actions with OIDC federation |
| Config Management | Ansible, Helm 3 |
| Containers | Docker multi-stage builds, ECR |

## License

MIT
