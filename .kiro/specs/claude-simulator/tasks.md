# Implementation Plan: Claude Simulator

## Overview

Build a full-stack AI chat platform replicating the Claude.ai experience. The implementation proceeds bottom-up: database models and core services first, then API endpoints, then frontend, then infrastructure and DevOps. Python (FastAPI + Hypothesis) for backend, TypeScript (Next.js + fast-check) for frontend.

## Tasks

- [x] 1. Set up project structure and core configuration
  - [x] 1.1 Create backend project skeleton
    - Create `backend/` directory with `app/main.py`, `app/core/config.py`, `app/core/dependencies.py`
    - Set up `requirements.txt` with FastAPI, uvicorn, SQLAlchemy, asyncpg, pgvector, pydantic-settings, boto3, hypothesis, pytest, pytest-asyncio, httpx, prometheus-fastapi-instrumentator
    - Create `backend/Dockerfile` with Python 3.12 slim multi-stage build
    - _Requirements: 12.2_

  - [x] 1.2 Create frontend project skeleton
    - Initialize Next.js 14+ app with App Router in `frontend/`
    - Install dependencies: next-auth or lightweight OIDC client, fast-check, jest, @testing-library/react, msw
    - Create `frontend/Dockerfile` with Node 20 Alpine multi-stage build
    - _Requirements: 12.1_

  - [x] 1.3 Create docker-compose.yml for local development
    - Define services: postgres (with pgvector), backend, frontend, keycloak
    - Configure networking and environment variables
    - _Requirements: 12.1, 12.2_

- [x] 2. Implement database models and schemas
  - [x] 2.1 Create SQLAlchemy ORM models
    - Implement `backend/app/models/orm.py` with Conversation, Message, Embedding, UserMemory, SessionSummary models
    - Implement `backend/app/models/database.py` with async engine, session factory, and Base
    - Include pgvector Vector(1536) columns, UUID primary keys, cascade deletes, check constraints
    - _Requirements: 1.5, 3.3, 3.4, 4.4, 5.2, 7.5_

  - [x] 2.2 Create Pydantic request/response schemas
    - Implement `backend/app/models/schemas.py` with ChatRequest, ConversationSummary, ConversationDetail, MessageResponse, MemoryCreateRequest, MemoryUpdateRequest, UserMemoryEntry, ImageGenRequest, ImageGenResponse, HealthResponse, ErrorResponse, ModelChoice enum
    - _Requirements: 1.6, 2.2, 9.4_

  - [x] 2.3 Create SQL migration script
    - Write `backend/migrations/001_initial.sql` with CREATE TABLE statements for conversations, messages, embeddings, user_memory, session_summaries
    - Include pgvector extension, indexes (ivfflat for vector columns, btree for timestamps)
    - _Requirements: 4.2, 5.2, 7.5_

- [x] 3. Implement core backend services
  - [x] 3.1 Implement Bedrock service
    - Create `backend/app/services/bedrock.py` with BedrockService class
    - Implement `stream_chat()` using `invoke_model_with_response_stream` with model mapping: "sonnet" → "anthropic.claude-sonnet-4-20250514", "opus" → "anthropic.claude-opus"
    - Implement `generate_embedding()` using Titan Embeddings v2 returning 1536-dim vectors
    - Implement `generate_image()` using Titan Image Generator returning PNG bytes
    - Implement `generate_summary()` for conversation summarization
    - _Requirements: 1.1, 1.2, 2.3, 2.5, 4.1, 9.1_

  - [x] 3.2 Write property test: Model identifier maps to correct Bedrock model
    - **Property 6: Model identifier maps to correct Bedrock model**
    - **Validates: Requirements 2.3, 2.5**

  - [x] 3.3 Implement text chunking utility
    - Create `backend/app/utils/chunking.py` with `chunk_text()` function
    - Split text into segments of ≤500 tokens, preserving content (no loss or duplication)
    - _Requirements: 4.4_

  - [x] 3.4 Write property test: Text chunking produces segments ≤ 500 tokens
    - **Property 11: Text chunking produces segments ≤ 500 tokens**
    - **Validates: Requirements 4.4**

  - [x] 3.5 Implement RAG service
    - Create `backend/app/services/rag.py` with RAGService class
    - Implement `retrieve_context()`: query pgvector across embeddings, user_memory, session_summaries tables; return top-5 results with cosine similarity ≥ 0.7, ordered by similarity descending
    - Implement `store_exchange()`: chunk user+assistant text via `chunk_text()`, embed each chunk, insert into embeddings table
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 5.5_

  - [x] 3.6 Write property test: RAG retrieval constraints
    - **Property 10: RAG retrieval constraints**
    - **Validates: Requirements 4.2, 4.5, 5.5**

  - [x] 3.7 Implement SSE streaming utility
    - Create `backend/app/utils/streaming.py` with SSE response helpers
    - Format chunks as `data: {json}\n\n` events for EventSource consumption
    - _Requirements: 1.2, 1.3_

- [x] 4. Implement authentication
  - [x] 4.1 Implement JWT validation middleware
    - Create `backend/app/core/auth.py` with JWTValidator class
    - Validate JWT access tokens against Keycloak JWKS endpoint with key caching
    - Return 401 on invalid/expired tokens
    - Create `get_current_user` dependency in `backend/app/core/dependencies.py`
    - _Requirements: 10.4, 10.5_

  - [x] 4.2 Write property test: JWT validation on every request
    - **Property 23: JWT validation on every request**
    - **Validates: Requirements 10.4, 10.5**

- [x] 5. Checkpoint — Core services
  - Ensure all tests pass, ask the user if questions arise.
  - **Deployment Increment 1 — Local Dev Stack**: Run `docker-compose up` and verify PostgreSQL + pgvector is running, backend connects to DB, migrations apply cleanly, and Bedrock service can reach AWS. This is your first "it works on my machine" moment.

- [x] 6. Implement backend API endpoints — Chat and Conversations
  - [x] 6.1 Implement POST /api/chat endpoint
    - Create `backend/app/api/chat.py`
    - Store user message → generate embedding → RAG retrieve context → build prompt with history + RAG context → stream Bedrock response via SSE → store assistant message → chunk+embed exchange
    - Auto-generate conversation title from first user message via Bedrock
    - Update `last_message_at` on conversation for idle tracking
    - _Requirements: 1.1, 1.2, 1.5, 3.5, 4.1, 4.2, 4.3, 4.4, 6.1, 6.5_

  - [x] 6.2 Write property test: Prompt includes conversation history and RAG context
    - **Property 1: Prompt includes conversation history and RAG context**
    - **Validates: Requirements 1.1, 4.3, 4.6**

  - [x] 6.3 Write property test: Bedrock errors produce structured error responses
    - **Property 4: Bedrock errors produce structured error responses**
    - **Validates: Requirements 1.6, 9.4**

  - [x] 6.4 Write property test: Auto-generated conversation title
    - **Property 9: Auto-generated conversation title**
    - **Validates: Requirements 3.5**

  - [x] 6.5 Write property test: Idle timer tracking
    - **Property 14: Idle timer tracking**
    - **Validates: Requirements 6.1, 6.5**

  - [x] 6.6 Implement conversation CRUD endpoints
    - Create `backend/app/api/conversations.py`
    - POST /api/conversations: create new conversation
    - GET /api/conversations: list conversations within 30-day window, ordered by updated_at DESC
    - GET /api/conversations/{id}: get full message history
    - DELETE /api/conversations/{id}: cascade delete conversation, messages, embeddings
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.6_

  - [x] 6.7 Write property test: Message persistence round-trip
    - **Property 3: Message persistence round-trip**
    - **Validates: Requirements 1.5, 3.3**

  - [x] 6.8 Write property test: Conversation listing is ordered by recency
    - **Property 7: Conversation listing is ordered by recency**
    - **Validates: Requirements 3.2**

  - [x] 6.9 Write property test: Conversation cascade deletion
    - **Property 8: Conversation cascade deletion**
    - **Validates: Requirements 3.4, 7.4**

  - [x] 6.10 Write property test: 30-day conversation filter
    - **Property 18: 30-day conversation filter**
    - **Validates: Requirements 7.1, 7.6**

- [x] 7. Implement backend API endpoints — Memory, Images, Health
  - [x] 7.1 Implement memory CRUD endpoints
    - Create `backend/app/api/memory.py`
    - GET /api/memory: list all user memory entries
    - POST /api/memory: create entry with embedding
    - PUT /api/memory/{id}: update entry, regenerate embedding
    - DELETE /api/memory/{id}: remove entry and embedding
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 7.2 Write property test: User memory CRUD round-trip
    - **Property 12: User memory CRUD round-trip**
    - **Validates: Requirements 5.2, 5.3**

  - [x] 7.3 Write property test: User memory deletion
    - **Property 13: User memory deletion**
    - **Validates: Requirements 5.4**

  - [x] 7.4 Implement image endpoints
    - Create `backend/app/api/images.py`
    - POST /api/images/generate: invoke Titan Image Generator, return base64 PNG
    - Add image upload validation: accept PNG/JPEG/GIF/WebP ≤ 5MB, reject others with 400
    - Handle multimodal messages: encode uploaded image as base64 in Bedrock request
    - Store image data with message (has_image=true, image_data populated)
    - _Requirements: 8.1, 8.2, 8.5, 8.6, 9.1, 9.2, 9.5_

  - [x] 7.5 Write property test: Image upload validation
    - **Property 20: Image upload validation**
    - **Validates: Requirements 8.1, 8.5**

  - [x] 7.6 Write property test: Image base64 encoding for Bedrock
    - **Property 21: Image base64 encoding for Bedrock**
    - **Validates: Requirements 8.2**

  - [x] 7.7 Write property test: Image persistence with messages
    - **Property 22: Image persistence with messages**
    - **Validates: Requirements 8.6, 9.5**

  - [x] 7.8 Implement health and metrics endpoints
    - Create `backend/app/api/health.py`
    - GET /api/health: check DB connectivity + Bedrock availability, return 200 or 503
    - Integrate prometheus-fastapi-instrumentator for /metrics endpoint with http_requests_total, http_request_duration_seconds, error rate counters
    - _Requirements: 11.1, 11.2, 11.5_

  - [x] 7.9 Write property test: Metrics endpoint produces valid Prometheus format
    - **Property 24: Metrics endpoint produces valid Prometheus format**
    - **Validates: Requirements 11.1**

- [x] 8. Implement session lifecycle management
  - [x] 8.1 Implement session manager service
    - Create `backend/app/services/session.py` with SessionManager class
    - Implement `track_activity()`: update last_message_at timestamp
    - Implement `check_idle_conversations()`: find conversations idle ≥ 5 minutes
    - Implement `generate_and_email_summary()`: generate summary via Bedrock, store in session_summaries, send via SES
    - Implement `run_expiry_job()`: daily job to find conversations >30 days old, archive to session_summaries, delete originals
    - _Requirements: 6.1, 6.2, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4_

  - [x] 8.2 Write property test: Idle summary generation trigger
    - **Property 15: Idle summary generation trigger**
    - **Validates: Requirements 6.2**

  - [x] 8.3 Write property test: Summary persistence regardless of email outcome
    - **Property 17: Summary persistence regardless of email outcome**
    - **Validates: Requirements 6.6**

  - [x] 8.4 Write property test: Expiry archival preserves summaries indefinitely
    - **Property 19: Expiry archival preserves summaries indefinitely**
    - **Validates: Requirements 7.2, 7.3, 7.5**

  - [x] 8.5 Implement email service
    - Create `backend/app/services/email.py` with EmailService class
    - Implement `send_session_summary()`: send HTML email via SES with retry up to 3 times with exponential backoff (1s, 2s, 4s)
    - _Requirements: 6.3, 6.4_

  - [x] 8.6 Write property test: Email retry with exponential backoff
    - **Property 16: Email retry with exponential backoff**
    - **Validates: Requirements 6.4**

- [x] 9. Wire up FastAPI application
  - [x] 9.1 Create main application entry point
    - Implement `backend/app/main.py`: create FastAPI app, register routers, add CORS middleware, add auth middleware, configure prometheus instrumentator, set up startup/shutdown events for DB pool and background tasks (idle checker, expiry job)
    - _Requirements: 1.1, 10.4, 11.1_

- [x] 10. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.
  - **Deployment Increment 2 — Backend API Running Locally**: Run the full backend via docker-compose with Keycloak. Verify: POST /api/chat streams a response from Bedrock, /api/health returns 200, /metrics returns Prometheus format, JWT auth rejects unauthenticated requests. Test with curl or Swagger UI at /docs.

- [x] 11. Implement frontend — Core chat UI
  - [x] 11.1 Implement auth integration
    - Create `frontend/src/lib/auth.ts` with Keycloak OIDC client (PKCE flow)
    - Handle login redirect, token storage, silent refresh, Bearer header injection
    - Redirect unauthenticated users to Keycloak login page
    - _Requirements: 10.1, 10.2, 10.3, 10.6_

  - [x] 11.2 Implement useChat hook with SSE streaming
    - Create `frontend/src/hooks/useChat.ts`
    - Open EventSource to POST /api/chat, append chunks to current message, expose { messages, sendMessage, isStreaming, error, retry }
    - Handle SSE connection drops: show error notification + retry button
    - _Requirements: 1.2, 1.3, 1.7_

  - [x] 11.3 Write property test: Chunk assembly produces correct message
    - **Property 2: Chunk assembly produces correct message**
    - **Validates: Requirements 1.3**

  - [x] 11.4 Implement ChatThread and MessageBubble components
    - Create `frontend/src/components/ChatThread.tsx` and `MessageBubble.tsx`
    - Render message thread with user/assistant bubbles, typing indicator during streaming
    - Display images inline within conversation thread
    - _Requirements: 1.3, 1.4, 8.4, 9.3_

  - [x] 11.5 Implement ChatInput component
    - Create `frontend/src/components/ChatInput.tsx`
    - Text input with send button, disabled while streaming
    - _Requirements: 1.1_

  - [x] 11.6 Implement ModelSelector component
    - Create `frontend/src/components/ModelSelector.tsx`
    - Toggle between Sonnet 4 (default) and Opus, display current selection
    - Send model identifier with chat requests
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [x] 11.7 Write property test: Model selection propagated in requests
    - **Property 5: Model selection propagated in requests**
    - **Validates: Requirements 2.2**

- [x] 12. Implement frontend — Conversations, Memory, Images
  - [x] 12.1 Implement ConversationSidebar component
    - Create `frontend/src/components/ConversationSidebar.tsx`
    - List conversations ordered by recency with title and timestamp
    - New conversation button, select conversation, delete conversation
    - Only show conversations within 30-day window
    - Display welcome prompt with suggested starters when conversation has zero messages
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 7.6_

  - [x] 12.2 Implement MemoryEditor component and Settings page
    - Create `frontend/src/components/MemoryEditor.tsx` and `frontend/src/app/settings/page.tsx`
    - Display all user memory entries with edit and delete controls
    - Text area for adding new entries, save triggers API call
    - _Requirements: 5.1, 5.6_

  - [x] 12.3 Implement ImageUpload component
    - Create `frontend/src/components/ImageUpload.tsx`
    - File picker accepting PNG/JPEG/GIF/WebP up to 5MB
    - Client-side validation: reject files >5MB or unsupported formats with error message
    - _Requirements: 8.1, 8.4, 8.5_

  - [x] 12.4 Implement main ChatPage layout
    - Create `frontend/src/app/page.tsx` wiring together ConversationSidebar, ChatThread, ChatInput, ModelSelector, ImageUpload
    - _Requirements: 1.1, 2.1, 3.1_

- [x] 13. Checkpoint — Frontend complete
  - Ensure all tests pass, ask the user if questions arise.
  - **Deployment Increment 3 — Full App Running Locally**: Run frontend + backend + Keycloak + PostgreSQL via docker-compose. Verify end-to-end: login via Keycloak → send a chat message → see streaming response → create/switch/delete conversations → upload an image → manage memory entries. This is the "demo-ready on localhost" milestone.

- [x] 14. Implement Terraform infrastructure
  - [x] 14.1 Create Terraform state backend module
    - Create `terraform/modules/state/` with S3 bucket + DynamoDB table for state locking
    - _Requirements: 13.2_

  - [x] 14.2 Create networking module
    - Create `terraform/modules/networking/` with VPC, public/private subnets, NAT gateway, route tables, security groups
    - RDS security group: allow inbound only from EKS security group
    - _Requirements: 13.1, 15.1_

  - [x] 14.3 Create EKS module
    - Create `terraform/modules/eks/` with EKS cluster, managed node group (t3.medium, 2-4 nodes), OIDC provider for IRSA
    - _Requirements: 12.3, 13.1_

  - [x] 14.4 Create RDS module
    - Create `terraform/modules/rds/` with PostgreSQL instance (db.t3.micro), subnet group, security group, pgvector extension, encryption at rest
    - _Requirements: 13.1, 15.1, 15.3_

  - [x] 14.5 Create ECR, ALB, IAM, and SES modules
    - Create `terraform/modules/ecr/` with frontend + backend repositories, lifecycle policies, image scanning on push
    - Create `terraform/modules/alb/` with ALB, target groups, listeners, path-based routing (/ → frontend, /api/* → backend, /auth/* → keycloak, /grafana/* → grafana), self-signed TLS cert
    - Create `terraform/modules/iam/` with IRSA roles for Bedrock, SES, ECR access; CI/CD OIDC role; EKS node role — all least-privilege
    - Create `terraform/modules/ses/` with email identity verification
    - _Requirements: 13.1, 15.2, 15.5, 15.6_

  - [x] 14.6 Create root Terraform configuration
    - Create `terraform/main.tf`, `terraform/variables.tf`, `terraform/outputs.tf` wiring all modules together
    - Configure S3 backend for state
    - _Requirements: 13.1, 13.2, 13.5_

- [x] 15. Implement Kubernetes manifests and Helm charts
  - [x] 15.1 Create application Helm charts
    - Create `k8s/frontend/` and `k8s/backend/` Helm charts with Deployment, Service, Ingress
    - Include resource requests/limits for CPU and memory
    - Include liveness and readiness probes (backend: /api/health, frontend: /)
    - Configure namespaces: claude-simulator, auth, monitoring
    - _Requirements: 12.3, 12.5, 12.6_

  - [x] 15.2 Create Keycloak Helm values
    - Create `k8s/keycloak/` with bitnami/keycloak Helm values
    - Configure realm, client (public, PKCE), single user, brute-force protection (5 attempts, 15 min lock), token lifetimes (access 5 min, refresh 30 min)
    - _Requirements: 10.2, 10.7_

  - [x] 15.3 Create monitoring Helm values
    - Create `k8s/monitoring/` with kube-prometheus-stack Helm values
    - Configure Prometheus scrape targets (backend /metrics, node-exporter, kube-state-metrics)
    - Configure Grafana dashboards: Backend API metrics, K8s cluster health, RDS performance, Bedrock usage
    - _Requirements: 11.1, 11.3, 11.4_

- [x] 16. Implement Ansible playbooks
  - [x] 16.1 Create Ansible roles and playbooks
    - Create `ansible/roles/helm-repos/` to add bitnami, prometheus-community Helm repos
    - Create `ansible/roles/monitoring/` to deploy kube-prometheus-stack and configure Grafana dashboards
    - Create `ansible/roles/keycloak/` to deploy Keycloak Helm chart and configure realm/client/user
    - Create `ansible/roles/application/` to deploy frontend + backend Helm charts and configure ingress
    - Create `ansible/roles/verify/` to health check all services
    - Create `ansible/playbooks/deploy.yml` orchestrating all roles
    - _Requirements: 13.3, 13.4, 13.6_

- [x] 17. Deployment Increment 4 — Infrastructure provisioned and configured
  - Run `terraform apply` to provision all AWS resources (VPC, EKS, RDS, ECR, ALB, IAM, SES)
  - Run Ansible playbooks to deploy Keycloak, Prometheus, Grafana, and app Helm charts to EKS
  - Verify: EKS cluster is healthy, RDS is accessible from pods, Keycloak admin console loads, Grafana dashboards show cluster metrics, ALB routes traffic correctly
  - **Deployment Increment 4 — Infra Provisioned**: This is the "cloud is ready" milestone. Everything runs on AWS but CI/CD isn't automated yet — you deployed manually via Ansible.

- [x] 18. Implement CI/CD pipeline
  - [x] 18.1 Create GitHub Actions workflow
    - Create `.github/workflows/deploy.yml`
    - On push to main: run pytest (backend) + jest (frontend) → build Docker images → push to ECR → update K8s deployments on EKS
    - Authenticate to AWS using OIDC federation (no long-lived credentials)
    - Halt and report on any stage failure
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x] 18.2 Create Kubernetes secrets configuration
    - Document and create K8s Secret manifests for RDS credentials, Keycloak admin, SES config
    - Ensure no credentials in source code or direct env vars
    - _Requirements: 15.4_

- [x] 19. Final checkpoint — Full stack integration
  - Ensure all tests pass, ask the user if questions arise.
  - **Deployment Increment 5 — Production on EKS**: Run the full CI/CD pipeline end-to-end. Push to main → tests pass → images built and pushed to ECR → K8s deployments updated → verify the app is live on the ALB URL. Confirm Grafana dashboards show real metrics, Keycloak login works, chat streams from Bedrock, session summaries email via SES. This is the "it's live" milestone.

## Deployment Increment Summary

| Increment | After Task | What You Deploy | What You Verify |
|-----------|-----------|-----------------|-----------------|
| 1 — Local Dev Stack | 5 | docker-compose (DB + backend) | DB connects, migrations run, Bedrock reachable |
| 2 — Backend API Local | 10 | docker-compose (full backend + Keycloak) | Chat streams, auth works, health/metrics endpoints |
| 3 — Full App Local | 13 | docker-compose (everything) | End-to-end: login → chat → images → memory |
| 4 — Infra Provisioned | 16 | Terraform apply + Ansible deploy | EKS cluster up, RDS accessible, Keycloak + monitoring running |
| 5 — Production on EKS | 18 | CI/CD pipeline push-to-deploy | Full app live on ALB, Grafana dashboards, SES emails |

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis (Python backend) and fast-check (TypeScript frontend)
- Checkpoints at tasks 5, 10, 13, and 18 ensure incremental validation
- Backend property tests cover Properties 1, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
- Frontend property tests cover Properties 2, 5, 20
