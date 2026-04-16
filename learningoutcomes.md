# Learning Outcomes — Claude Simulator

Things you flagged as "I need to learn this." This is your study guide while the project gets built.

---

## Frontend — Next.js & React

**What you need to learn:**
- React fundamentals: components, props, state, hooks (useState, useEffect, useRef)
- JSX syntax — it's HTML-like but inside JavaScript
- Next.js App Router — how pages and layouts work via the file system
- Server Components vs Client Components (Next.js 14+ concept)
- How streaming responses work in a chat UI (Server-Sent Events / SSE)
- Tailwind CSS basics (utility-first CSS framework, pairs great with Next.js)

**Resources:**
- [React docs (new)](https://react.dev/learn) — start here, it's excellent
- [Next.js Learn course](https://nextjs.org/learn) — official interactive tutorial
- [Tailwind CSS docs](https://tailwindcss.com/docs) — reference as you go

---

## Backend — Python + FastAPI

**What you need to learn:**
- FastAPI basics: routes, request/response models, dependency injection
- Pydantic models (data validation — FastAPI uses these heavily)
- Async/await in Python (FastAPI is async-first)
- How to stream responses from Bedrock through FastAPI to the frontend
- SQLAlchemy (ORM for PostgreSQL)

**Resources:**
- [FastAPI official tutorial](https://fastapi.tiangolo.com/tutorial/) — one of the best docs in Python
- [Pydantic docs](https://docs.pydantic.dev/)

---

## Vector Search & RAG

**What you need to learn:**
- What embeddings are — turning text into numbers that capture meaning
- How vector similarity search works (cosine similarity)
- pgvector — PostgreSQL extension that stores and queries embeddings
- RAG pattern: retrieve relevant context → inject into LLM prompt → get better answers
- Chunking strategies — how to split conversations into searchable pieces

**Resources:**
- [pgvector GitHub](https://github.com/pgvector/pgvector) — setup and usage
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings) — concepts apply to any embedding model
- AWS Bedrock Titan Embeddings docs

---

## Authentication — Keycloak

**What you need to learn:**
- What Keycloak is: open-source identity and access management (IAM)
- Realms, clients, users, roles — Keycloak's core concepts
- OIDC (OpenID Connect) flow — how login/logout/token refresh works
- How to deploy Keycloak on Kubernetes
- How to integrate Keycloak with a Next.js frontend and FastAPI backend

**Resources:**
- [Keycloak Getting Started](https://www.keycloak.org/getting-started/getting-started-kube)
- [Keycloak Admin Guide](https://www.keycloak.org/docs/latest/server_admin/)

---

## Kubernetes (EKS)

**What you need to learn:**
- Core K8s concepts: Pods, Deployments, Services, Ingress, ConfigMaps, Secrets
- Helm charts — package manager for Kubernetes
- EKS specifics: node groups, IAM roles for service accounts (IRSA)
- kubectl commands — your daily driver for interacting with the cluster
- Namespace organization

**Resources:**
- [Kubernetes official tutorials](https://kubernetes.io/docs/tutorials/)
- [EKS Workshop](https://www.eksworkshop.com/)

---

## Docker

**What you need to learn:**
- Dockerfile syntax — how to containerize your apps
- Multi-stage builds (smaller, more secure images)
- Docker Compose for local development
- ECR (Elastic Container Registry) — where your images live on AWS

**Resources:**
- [Docker getting started](https://docs.docker.com/get-started/)

---

## CI/CD Pipeline

**What you need to learn:**
- GitHub Actions or AWS CodePipeline (pick one)
- Build → Test → Push Image → Deploy to K8s flow
- Environment variables and secrets management in CI/CD

---

## Monitoring — Prometheus & Grafana

**What you need to learn:**
- Prometheus: metrics collection, PromQL (query language), scrape configs
- Grafana: dashboards, data sources, alerting
- How to instrument a FastAPI app with Prometheus metrics
- Kubernetes monitoring with kube-prometheus-stack (Helm chart)

**Resources:**
- [Prometheus docs](https://prometheus.io/docs/introduction/overview/)
- [Grafana tutorials](https://grafana.com/tutorials/)

---

## Ansible

**What you need to learn:**
- Playbooks, roles, inventory files
- How to use Ansible for infrastructure provisioning alongside Terraform/CloudFormation
- Ansible + AWS modules

**Resources:**
- [Ansible getting started](https://docs.ansible.com/ansible/latest/getting_started/)

---

## AWS Services You'll Use

| Service | Purpose | Learn Priority |
|---------|---------|---------------|
| Bedrock | LLM (Claude) + Image Gen (Titan) + Embeddings | High |
| EKS | Kubernetes cluster | High |
| ECR | Container image registry | Medium |
| RDS (PostgreSQL) | Database + pgvector | High |
| SES | Email session summaries | Low |
| IAM | Permissions, IRSA | High |
| Route 53 | DNS (if you get a domain) | Low |
| ACM | SSL certificates | Low |
| CloudWatch | Logs (complement to Prometheus) | Medium |

---

## Study Order (Suggested)

1. **Docker** — you need this to build anything
2. **Python + FastAPI** — get the backend running locally
3. **React + Next.js** — get the frontend running locally
4. **PostgreSQL + pgvector** — understand your data layer
5. **Kubernetes basics** — before touching EKS
6. **EKS** — deploy your app
7. **Keycloak** — add auth
8. **Prometheus + Grafana** — add monitoring
9. **CI/CD** — automate everything
10. **Ansible** — infrastructure automation
