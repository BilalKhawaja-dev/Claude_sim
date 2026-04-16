# Claude Simulator — Architecture Document

## Overview

Claude Simulator is a single-user AI chat platform replicating the Claude.ai experience, powered by AWS Bedrock Claude models. The system runs entirely on AWS infrastructure, deployed on EKS with a full DevOps pipeline including CI/CD, monitoring, and infrastructure-as-code.

---

## Architecture Pattern: Microservices on Kubernetes

**Why microservices over monolith?**
- Each component (frontend, backend API, Keycloak, monitoring) runs as an independent service on K8s
- Services can be scaled, updated, and debugged independently
- Demonstrates real-world K8s patterns for portfolio value
- Trade-off: More complex than a monolith, but this complexity IS the portfolio showcase

**Why NOT a monolith?**
- A monolith would be simpler and cheaper to run
- For a single-user app, a monolith is technically sufficient
- We chose microservices because the goal is to demonstrate DevOps skills, not minimize complexity

---

## Network Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────┐
│  AWS Application Load Balancer  │
│  (ALB with self-signed cert)    │
│  - TLS termination              │
│  - Path-based routing           │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│                  EKS Cluster                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Next.js  │  │ FastAPI  │  │  Keycloak    │  │
│  │ Frontend │  │ Backend  │  │  Auth Server │  │
│  │ :3000    │  │ :8000    │  │  :8080       │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │ Prometheus   │  │ Grafana                │   │
│  │ :9090        │  │ :3000                  │   │
│  └──────────────┘  └────────────────────────┘   │
│                                                  │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│              AWS Managed Services                │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ RDS      │  │ Bedrock  │  │  SES         │  │
│  │ Postgres │  │ Claude + │  │  Email       │  │
│  │ +pgvector│  │ Titan    │  │  Service     │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────┐  ┌──────────┐                     │
│  │ ECR      │  │ IAM      │                     │
│  │ Registry │  │ Roles    │                     │
│  └──────────┘  └──────────┘                     │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Application Load Balancer (ALB)

**Why ALB over NLB (Network Load Balancer)?**
- ALB operates at Layer 7 (HTTP/HTTPS) — we need path-based routing
- Routes `/` → Next.js frontend
- Routes `/api/*` → FastAPI backend
- Routes `/auth/*` → Keycloak
- Routes `/grafana/*` → Grafana dashboard
- NLB operates at Layer 4 (TCP) — no path routing, would need separate load balancers

**Why ALB over NGINX Ingress?**
- AWS ALB Ingress Controller integrates natively with EKS
- Automatic health checks, SSL termination, and AWS WAF integration
- NGINX Ingress would work but adds another component to manage
- ALB is the AWS-native choice — simpler IAM integration

**SSL/TLS:**
- Self-signed certificate (no domain available)
- TLS termination at ALB — traffic inside the cluster is HTTP (standard K8s pattern)
- Trade-off: Browser will show security warning. Acceptable for single-user personal use

**Terraform resource:** `aws_lb`, `aws_lb_target_group`, `aws_lb_listener`

---

### 2. EKS (Elastic Kubernetes Service)

**Why EKS over self-managed K8s (k3s/kubeadm)?**
- EKS manages the control plane (API server, etcd, scheduler) — you don't patch or maintain it
- Integrates with IAM, ALB, CloudWatch natively
- Industry standard — this is what companies actually use
- Trade-off: Costs ~$0.10/hr ($73/month) for the control plane alone

**Why EKS over ECS (Elastic Container Service)?**
- ECS is simpler and cheaper, but it's AWS-proprietary
- Kubernetes skills transfer across all cloud providers
- K8s has a richer ecosystem (Helm, Prometheus, Grafana, Keycloak all have K8s-native deployments)
- Portfolio value: K8s >> ECS in the job market

**Node Group Configuration:**
- Managed node group with `t3.medium` instances (2 vCPU, 4GB RAM)
- Start with 2 nodes (minimum for HA), max 4 for autoscaling
- Trade-off: `t3.medium` is the sweet spot — `t3.small` is too tight for Keycloak + monitoring stack

**Namespaces:**
```
├── claude-simulator    # Frontend + Backend + app configs
├── auth                # Keycloak
├── monitoring          # Prometheus + Grafana
└── kube-system         # EKS system components
```

**Terraform resources:** `aws_eks_cluster`, `aws_eks_node_group`, `aws_iam_role`

---

### 3. Next.js Frontend

**Why Next.js over plain React (CRA/Vite)?**
- Server-side rendering (SSR) for faster initial page loads
- API routes built in — can proxy requests to FastAPI if needed
- File-based routing — cleaner project structure
- App Router (Next.js 14+) — modern React Server Components
- Trade-off: Slightly more complex than plain React, but the structure pays off

**Key Frontend Features:**
- Chat interface with streaming response display (Server-Sent Events)
- Model toggle (Sonnet 4 ↔ Opus) in the UI
- Conversation sidebar (list of saved sessions)
- Settings page with memory text box
- Image upload support (drag & drop or file picker)
- Image display for generated images
- Responsive design (works on mobile too)

**Streaming Pattern:**
```
User types message
    → POST /api/chat (with conversation history + RAG context)
    → FastAPI streams response via SSE
    → Next.js renders tokens as they arrive (typewriter effect)
```

**Container:** Node 20 Alpine image, ~150MB
**K8s:** Deployment with 1 replica, Service (ClusterIP), Ingress rule on ALB

---

### 4. FastAPI Backend

**Why FastAPI over Flask/Django?**
- Native async support — critical for streaming Bedrock responses without blocking
- Automatic OpenAPI/Swagger docs at `/docs` — great for development and portfolio
- Pydantic models for request/response validation — catches bugs early
- Performance: FastAPI is one of the fastest Python frameworks
- Trade-off: Smaller community than Flask/Django, but growing rapidly

**API Endpoints (planned):**
```
POST   /api/chat                  # Send message, get streaming response
GET    /api/conversations         # List all conversations
GET    /api/conversations/{id}    # Get conversation history
DELETE /api/conversations/{id}    # Delete a conversation
POST   /api/conversations         # Create new conversation
PUT    /api/memory                # Update user memory settings
GET    /api/memory                # Get current memory text
POST   /api/images/generate       # Generate image via Titan
GET    /api/health                # Health check for K8s probes
```

**Bedrock Integration Pattern:**
```python
# Streaming pattern with Bedrock
bedrock_client = boto3.client('bedrock-runtime')
response = bedrock_client.invoke_model_with_response_stream(
    modelId="anthropic.claude-sonnet-4-20250514",  # or opus
    body=json.dumps({
        "messages": [...],
        "max_tokens": 4096,
        "anthropic_version": "bedrock-2023-05-31"
    })
)
# Stream chunks back to frontend via SSE
```

**RAG Flow (on every chat message):**
1. User sends message
2. Backend generates embedding of the message using Titan Embeddings
3. Query pgvector for similar past conversation chunks + user memory
4. Inject relevant context into the system prompt
5. Send to Bedrock Claude with augmented context
6. Stream response back to user
7. After response complete, chunk and store the exchange in pgvector

**Container:** Python 3.12 slim image, ~200MB
**K8s:** Deployment with 1 replica, Service (ClusterIP), Ingress rule on ALB

---

### 5. RDS PostgreSQL + pgvector

**Why RDS over self-managed PostgreSQL on K8s?**
- RDS handles backups, patching, failover automatically
- Running databases on K8s is an anti-pattern for production (stateful workloads on K8s are painful)
- RDS Multi-AZ gives you automatic failover
- Trade-off: Costs more than self-managed, but worth it for reliability

**Why PostgreSQL over DynamoDB?**
- pgvector extension — vector search in the same database as relational data
- DynamoDB has no native vector search capability
- SQL is more flexible for complex queries (conversation history, session management)
- Trade-off: DynamoDB would be cheaper and fully serverless, but can't do vector search

**Why pgvector over a dedicated vector DB (Pinecone, Weaviate)?**
- One database for everything — simpler operations
- pgvector performance is excellent for single-user scale (millions of vectors)
- No additional service to manage, pay for, or monitor
- Runs on AWS (RDS) — stays in the ecosystem
- Trade-off: At massive scale (billions of vectors), dedicated vector DBs perform better. Irrelevant for single-user.

**Schema Design (high level):**
```sql
-- Conversations
conversations (id, title, created_at, updated_at, summary)

-- Messages within conversations
messages (id, conversation_id, role, content, created_at, has_image)

-- Vector embeddings for RAG
embeddings (id, conversation_id, chunk_text, embedding vector(1536), created_at)

-- User memory (manually added facts)
user_memory (id, content, embedding vector(1536), created_at, updated_at)

-- Session summaries (kept after 30-day UI deletion)
session_summaries (id, conversation_id, summary_text, embedding vector(1536), created_at)
```

**pgvector query pattern:**
```sql
SELECT chunk_text, 1 - (embedding <=> query_embedding) AS similarity
FROM embeddings
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

**Instance:** `db.t3.micro` or `db.t3.small` (single user doesn't need more)
**Terraform resources:** `aws_db_instance`, `aws_db_subnet_group`, `aws_security_group`

---

### 6. Keycloak (Authentication)

**Why Keycloak over simple JWT auth?**
- Full OIDC (OpenID Connect) implementation — industry standard auth protocol
- Admin console for user management
- Token refresh, session management, brute-force protection built in
- Portfolio value: demonstrates enterprise-grade identity management
- Trade-off: Heavy (~512MB-1GB RAM), complex config. Overkill for single-user, but impressive

**Auth Flow:**
```
User opens app
    → Next.js redirects to Keycloak login page
    → User enters credentials
    → Keycloak issues JWT (access token + refresh token)
    → Next.js stores tokens
    → Every API call includes Bearer token
    → FastAPI validates token against Keycloak's JWKS endpoint
    → Token expires → refresh token gets new access token silently
```

**Keycloak Configuration:**
- Single realm: `claude-simulator`
- Single client: `claude-simulator-app` (public client, PKCE flow)
- Single user: you
- HTTPS required: disabled (behind ALB with self-signed cert)

**K8s Deployment:**
- Runs in `auth` namespace
- Uses RDS PostgreSQL as its database (separate schema/database from app data)
- Helm chart: `bitnami/keycloak`

---

### 7. AWS Bedrock

**Models Used:**

| Model | Purpose | Why |
|-------|---------|-----|
| Claude Sonnet 4 | Default chat model | Fast, cost-effective, great quality |
| Claude Opus | Toggle option | Highest quality, slower, more expensive |
| Titan Embeddings v2 | Text → vector embeddings | AWS-native, good quality, cheap |
| Titan Image Generator | Image generation | AWS-native, no external API needed |

**Why Bedrock over direct Anthropic API?**
- All AWS — IAM-based auth, no API keys to manage
- Uses IRSA (IAM Roles for Service Accounts) — K8s pod gets AWS permissions automatically
- VPC endpoints available — traffic never leaves AWS network
- Trade-off: Slightly higher latency than direct API, but security and simplicity win

**Cost Estimates (Bedrock):**
- Sonnet 4: ~$3/M input tokens, ~$15/M output tokens
- Opus: ~$15/M input tokens, ~$75/M output tokens
- Titan Embeddings: ~$0.02/M tokens
- Titan Image: ~$0.01/image
- For single-user casual use: probably $5-20/month

---

### 8. SES (Simple Email Service)

**Why SES over SNS for email?**
- SES is purpose-built for email — HTML templates, attachments, delivery tracking
- SNS is for notifications (push, SMS, email) but email formatting is limited
- SES gives you rich HTML emails for session summaries
- Trade-off: SES requires email verification (you verify your own email address). No domain needed for sending to yourself.

**Flow:**
```
5 minutes of chat idle detected
    → Backend generates AI summary of the session
    → Summary formatted as HTML email
    → SES sends to your verified email address
```

**Terraform resources:** `aws_ses_email_identity`, `aws_ses_template`

---

### 9. ECR (Elastic Container Registry)

**Why ECR over Docker Hub?**
- AWS-native — EKS pulls images from ECR with IAM auth (no Docker Hub credentials)
- Private by default — your images aren't public
- Integrated with GitHub Actions via OIDC (no long-lived AWS credentials in CI)
- Trade-off: None really. ECR is the obvious choice for EKS workloads.

**Repositories:**
```
claude-simulator/frontend    # Next.js image
claude-simulator/backend     # FastAPI image
```

**Terraform resources:** `aws_ecr_repository`, `aws_ecr_lifecycle_policy`

---

### 10. Prometheus + Grafana (Monitoring)

**Why Prometheus over CloudWatch?**
- Prometheus is the K8s-native monitoring standard
- PromQL is more powerful than CloudWatch Insights
- Grafana dashboards are more flexible and beautiful than CloudWatch dashboards
- Learning Prometheus/Grafana is a career skill — CloudWatch is AWS-only knowledge
- Trade-off: Runs on your cluster (uses resources). CloudWatch would be zero-infra but less impressive.

**Deployment:**
- `kube-prometheus-stack` Helm chart — installs Prometheus, Grafana, Alertmanager, and node-exporter in one shot
- Runs in `monitoring` namespace

**What We Monitor:**
- K8s cluster health (node CPU, memory, pod status)
- FastAPI metrics (request latency, error rates, active connections)
- Bedrock API latency and error rates
- RDS metrics (connections, query latency, storage)
- Keycloak metrics (login attempts, token issuance)

**Custom FastAPI Metrics (using prometheus-fastapi-instrumentator):**
```python
# Automatically instruments all endpoints with:
# - http_request_duration_seconds (histogram)
# - http_requests_total (counter)
# - http_request_size_bytes (histogram)
# - http_response_size_bytes (histogram)
```

**Grafana Dashboards:**
- K8s Cluster Overview
- FastAPI Application Metrics
- Bedrock Usage & Latency
- PostgreSQL Performance

---

### 11. CI/CD — GitHub Actions

**Why GitHub Actions over AWS CodePipeline?**
- More developer-friendly YAML syntax
- Massive marketplace of pre-built actions
- Better community support and documentation
- Free for public repos, generous free tier for private
- Trade-off: Not AWS-native, but integrates well via OIDC federation (no long-lived credentials)

**Pipeline Flow:**
```
Push to main branch
    → Run tests (pytest for backend, jest for frontend)
    → Build Docker images
    → Push to ECR
    → Update K8s deployments on EKS (kubectl set image)
    → Run smoke tests
```

**Security:**
- OIDC federation between GitHub and AWS (no access keys stored in GitHub)
- Separate IAM role for CI/CD with minimal permissions
- Image scanning in ECR before deployment

---

### 12. Terraform (Infrastructure Provisioning)

**What Terraform Creates:**
```
├── VPC + Subnets (public + private)
├── EKS Cluster + Node Group
├── RDS PostgreSQL Instance
├── ECR Repositories
├── ALB + Target Groups + Listeners
├── IAM Roles (EKS, IRSA, CI/CD)
├── Security Groups
├── SES Email Identity
└── S3 Bucket (Terraform state)
```

**State Management:**
- Terraform state stored in S3 bucket with DynamoDB locking
- Prevents state corruption when running from multiple machines

**Terraform resources:** `aws_s3_bucket` (state), `aws_dynamodb_table` (lock)

---

### 13. Ansible (Configuration Management)

**What Ansible Configures (after Terraform provisions):**
```
├── Install Helm on local machine
├── Add Helm repositories
├── Deploy kube-prometheus-stack (Prometheus + Grafana)
├── Deploy Keycloak via Helm
├── Configure Keycloak realm, client, user
├── Deploy application Helm charts (frontend + backend)
├── Configure Grafana dashboards
└── Verify all services are healthy
```

**Why Ansible for this (instead of just Helm commands)?**
- Reproducible — run the playbook and everything is configured identically every time
- Idempotent — safe to run multiple times
- Documents the setup process as code
- Portfolio value: shows you know configuration management

---

## Session Lifecycle — Detailed Flow

```
1. User starts new conversation
   → New row in `conversations` table
   → Frontend opens SSE connection

2. User sends messages, AI responds
   → Messages stored in `messages` table
   → Each exchange chunked and embedded → stored in `embeddings` table
   → RAG context pulled from pgvector on each new message

3. 5 minutes of idle detected
   → Backend calls Bedrock to generate session summary
   → Summary sent via SES to user's email
   → Idle timer resets if user returns

4. Session visible in UI for 30 days
   → After 30 days, background job triggers
   → Session summary generated (if not already)
   → Summary + embedding stored in `session_summaries` table
   → Conversation and messages deleted from `conversations` and `messages` tables
   → Embeddings from `embeddings` table deleted
   → Summary persists forever in `session_summaries` for long-term RAG memory
```

---

## Memory System — Detailed Flow

```
Two sources of memory:

1. Manual Memory (Settings Page)
   → User types facts in a text box: "I prefer Python", "My name is X"
   → Each fact stored in `user_memory` table with embedding
   → Always included in RAG retrieval
   → User can edit/delete anytime

2. Automatic Memory (Session Summaries)
   → After 30-day session expiry, summary stored in `session_summaries`
   → Included in RAG retrieval based on relevance
   → Provides long-term context about past conversations

RAG Retrieval (on every message):
   → Query pgvector across BOTH tables
   → Top-K results injected into system prompt
   → AI responds with personalized context
```

---

## Security Architecture

| Layer | Mechanism | Details |
|-------|-----------|---------|
| Network | VPC + Security Groups | RDS only accessible from EKS. No public access. |
| Auth | Keycloak OIDC | JWT tokens, PKCE flow, brute-force protection |
| API | Bearer token validation | Every FastAPI endpoint validates JWT |
| AWS | IRSA | Pods get AWS permissions via K8s service accounts |
| CI/CD | OIDC Federation | GitHub Actions authenticates to AWS without stored credentials |
| Data | Encryption at rest | RDS encryption enabled, EBS encryption on EKS nodes |
| Transit | TLS | ALB terminates TLS, internal traffic in VPC |
| Images | ECR scanning | Vulnerability scanning on push |
| Secrets | K8s Secrets + AWS Secrets Manager | No hardcoded credentials anywhere |

---

## Cost Estimate (Monthly)

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| EKS Control Plane | $73 | Fixed cost |
| EC2 (2x t3.medium) | $60 | Node group |
| RDS (db.t3.micro) | $15 | Single-AZ to save cost |
| Bedrock (Claude) | $5-20 | Depends on usage |
| ECR | $1 | Image storage |
| SES | $0.10 | Pennies for single-user |
| ALB | $16 | Fixed + per-request |
| S3 (Terraform state) | $0.02 | Negligible |
| **Total** | **~$170-185/month** | |

**Cost optimization options:**
- Use Spot Instances for EKS nodes (save ~60% on EC2, risk of interruption)
- Use `db.t3.micro` with free tier if available
- Scale down to 1 node during off-hours

---

## Directory Structure (Planned)

```
claude_simulator/
├── frontend/                  # Next.js app
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── backend/                   # FastAPI app
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── terraform/                 # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── eks.tf
│   ├── rds.tf
│   └── ...
├── ansible/                   # Configuration management
│   ├── playbooks/
│   └── roles/
├── k8s/                       # Kubernetes manifests / Helm charts
│   ├── frontend/
│   ├── backend/
│   └── monitoring/
├── .github/workflows/         # CI/CD
│   └── deploy.yml
├── architecture.md            # This file
├── learningoutcomes.md        # Study guide
└── docker-compose.yml         # Local development
```
