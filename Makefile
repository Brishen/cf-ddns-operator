## Variables — override on the command line or in the environment.
REGISTRY       ?= ghcr.io/brishen
IMAGE          ?= $(REGISTRY)/cf-ddns-operator
TAG            ?= latest
CONTAINER_TOOL ?= docker   # set to "podman" if preferred

.DEFAULT_GOAL := help

.PHONY: help build push image install-crds install uninstall uninstall-crds run lint

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

build: ## Build the container image
	$(CONTAINER_TOOL) build -t $(IMAGE):$(TAG) .

push: ## Push the image to the registry
	$(CONTAINER_TOOL) push $(IMAGE):$(TAG)

image: build push ## Build and push the image

install-crds: ## Apply the CRD to the cluster
	kubectl apply -k deploy/crds/

install: ## Apply the operator (namespace, RBAC, Deployment)
	kubectl apply -k deploy/app/

uninstall: ## Remove the operator from the cluster
	kubectl delete -k deploy/app/

uninstall-crds: ## Remove the CRD — also deletes all CloudflareDNSRecord objects
	kubectl delete -k deploy/crds/

run: ## Run the operator locally against the current kubeconfig
	kopf run -m cf_ddns_operator.operator --verbose

lint: ## Run ruff linter
	ruff check src/
