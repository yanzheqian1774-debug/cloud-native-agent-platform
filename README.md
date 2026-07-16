# Cloud Native Multi-Agent Platform

从零构建一个 Kubernetes Native、模型可插拔的多智能体平台。

## 项目目标

本项目将实现：

- Agent CRD
- Kubernetes Operator
- Agent Runtime
- Multi-Agent Workflow
- API Gateway
- Qwen OpenAI-Compatible API
- 本地 kind 环境
- 公有云部署
- 日志、监控和 CI/CD

## 核心角色

- orchestrator
- researcher
- architect
- builder
- tester
- reviewer
- writer

## 技术栈

- macOS Apple Silicon
- Docker Desktop
- Kubernetes
- kind
- Python 3.12
- uv
- FastAPI
- Kopf
- Qwen
- PostgreSQL
- Redis

## 项目结构

```text
cloud-native-agent-platform/
├── docs/
├── adr/
├── architecture/
├── examples/
├── manifests/
├── operator/
├── runtime/
├── gateway/
├── workflow/
├── helm/
├── scripts/
├── tests/
└── .github/

## Local Development

### Prerequisites

- Python 3.12
- uv
- Git

### Setup

```bash
make setup














