SHELL := /usr/bin/env bash
ENVIRONMENT ?= local
export ENVIRONMENT

PYTHON_IMAGE := python:3.13-slim
ERROR_RATE ?= 0.3
LATENCY_MS ?= 0
VUS ?= 30

.DEFAULT_GOAL := help

.PHONY: help
help: ## List the available commands
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: deps
deps: ## Install Docker, kind, kubectl, Terraform and Helm
	@scripts/install-deps.sh

.PHONY: up
up: ## Create everything: state backend, cluster, observability and app
	@scripts/up.sh

.PHONY: down
down: ## Destroy the platform and the cluster (keeps the state backend)
	@scripts/down.sh

.PHONY: purge
purge: ## Destroy everything, including the state backend and .data
	@PURGE=1 scripts/down.sh

.PHONY: state-backend
state-backend: ## Start only the local S3 backend for Terraform state
	@scripts/state-backend.sh up

.PHONY: plan
plan: ## Show the plan for the platform stack
	@scripts/tf.sh platform plan

.PHONY: smoke-test
smoke-test: ## Check app, metrics, logs, traces and alerting
	@scripts/smoke-test.sh

.PHONY: credentials
credentials: ## Print URLs and passwords
	@scripts/tf.sh platform output urls
	@echo "RuminApp: admin / $$(scripts/tf.sh platform output -raw ruminapp_admin_password)"
	@echo "Grafana:  admin / $$(scripts/tf.sh platform output -raw grafana_admin_password)"

.PHONY: chaos
chaos: ## Inject faults into reproducao (ERROR_RATE=0.3 LATENCY_MS=0)
	@scripts/tf.sh platform apply -auto-approve -var 'chaos={error_rate=$(ERROR_RATE),latency_ms=$(LATENCY_MS)}'

.PHONY: chaos-off
chaos-off: ## Stop injecting faults
	@scripts/tf.sh platform apply -auto-approve

.PHONY: load
load: ## Raise the k6 load to watch the HPA scale (VUS=30)
	@scripts/tf.sh platform apply -auto-approve -var 'loadgen={enabled=true,vus=$(VUS),write_ratio=0.05}'

.PHONY: user
user: ## Issue a kubeconfig for an RBAC user (NAME=ana GROUP=ruminapp-developers)
	@scripts/kubeconfig-user.sh $(NAME) $(GROUP)

.PHONY: test
test: ## Run the service unit tests (in containers)
	@docker run --rm -v "$(CURDIR)/app:/src" -w /src/reproducao $(PYTHON_IMAGE) \
		sh -c "pip install -q --root-user-action=ignore -r requirements-dev.txt && PYTHONDONTWRITEBYTECODE=1 METRICS_PORT=0 python -m pytest -q -p no:cacheprovider"
	@docker run --rm -v "$(CURDIR)/app:/src" -w /src/web $(PYTHON_IMAGE) \
		sh -c "pip install -q --root-user-action=ignore -r requirements-dev.txt && PYTHONPATH=/src/reproducao METRICS_PORT=0 LOG_LEVEL=CRITICAL PYTHONDONTWRITEBYTECODE=1 python manage.py test rebanho"

.PHONY: lint
lint: ## terraform fmt/validate and shellcheck
	@terraform fmt -check -recursive
	@for stack in cluster platform; do \
		export TF_DATA_DIR=.terraform-validate; \
		terraform -chdir=infra/stacks/$$stack init -backend=false -input=false >/dev/null && \
		terraform -chdir=infra/stacks/$$stack validate -no-color; \
	done
	@if command -v shellcheck >/dev/null; then shellcheck scripts/*.sh; \
	else docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck:v0.11.0 scripts/*.sh; fi
