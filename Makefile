# Amazon Flex Route Optimizer — dev / build / deploy shortcuts
# Run `make` (or `make help`) to see all targets.

SHELL := /bin/bash

# ortools ships wheels for 3.10–3.13; prefer 3.13 if installed.
PYTHON   ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
BACKEND  := backend
FRONTEND := frontend
VENV     := $(BACKEND)/venv
VPY      := $(VENV)/bin/python
API_PORT ?= 8000
WEB_PORT ?= 5500
IMAGE    ?= flex-api
API_URL  ?= http://localhost:$(API_PORT)

.DEFAULT_GOAL := help
.PHONY: help install env-check api web dev smoke demo docker-build docker-run docker-stop \
        deploy-api deploy-web clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
	  /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Setup -------------------------------------------------------------------

$(VENV)/.installed: $(BACKEND)/requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VPY) -m pip install --upgrade pip -q
	$(VPY) -m pip install -r $(BACKEND)/requirements.txt -q
	@touch $@

install: $(VENV)/.installed ## Create backend venv and install dependencies

env-check: ## Make sure backend/.env has GOOGLE_MAPS_API_KEY
	@grep -qE '^GOOGLE_MAPS_API_KEY=.+' $(BACKEND)/.env 2>/dev/null || { \
	  echo "Missing $(BACKEND)/.env — create it with:"; \
	  echo "  echo 'GOOGLE_MAPS_API_KEY=your_server_key' > $(BACKEND)/.env"; exit 1; }

# --- Run locally ---------------------------------------------------------------

api: install env-check ## Run the FastAPI backend with auto-reload (port 8000)
	cd $(BACKEND) && venv/bin/uvicorn main:app --reload --port $(API_PORT)

web: ## Serve the static frontend (port 5500, allowed by CORS)
	@echo "Frontend → http://localhost:$(WEB_PORT)"
	cd $(FRONTEND) && $(PYTHON) -m http.server $(WEB_PORT)

dev: install env-check ## Run backend + frontend together (Ctrl-C stops both)
	@echo "API → $(API_URL)/docs   Frontend → http://localhost:$(WEB_PORT)"
	@trap 'kill 0' INT TERM EXIT; \
	  (cd $(BACKEND) && venv/bin/uvicorn main:app --reload --port $(API_PORT)) & \
	  (cd $(FRONTEND) && $(PYTHON) -m http.server $(WEB_PORT)) & \
	  wait

smoke: ## Hit the health endpoint of a running API (API_URL=...)
	@curl -fsS $(API_URL)/ && echo

demo: ## POST the built-in demo shift to a running API and print savings
	@curl -fsS -X POST $(API_URL)/optimize -H 'Content-Type: application/json' -d '{ \
	  "start": "Georgia Aquarium, Atlanta, GA", \
	  "stops": ["Piedmont Park, Atlanta, GA", "Ponce City Market, Atlanta, GA", \
	            "Fox Theatre, Atlanta, GA", "Mercedes-Benz Stadium, Atlanta, GA", \
	            "World of Coca-Cola, Atlanta, GA", "Atlanta Botanical Garden, Atlanta, GA", \
	            "Oakland Cemetery, Atlanta, GA", "Lenox Square, Atlanta, GA"]}' \
	| $(PYTHON) -c 'import json,sys; d=json.load(sys.stdin); \
	  a=d.get("algorithms") or sys.exit(d.get("error")); o=a["original"]["distance_m"]; \
	  [print("%-17s %7.2f mi  %5.1f%% saved  %8.1f ms" % (k, v["distance_mi"], 100*(o-v["distance_m"])/o, v["time_ms"])) \
	   for k, v in a.items()]'

# --- Docker ------------------------------------------------------------------

docker-build: ## Build the backend Docker image
	docker build -t $(IMAGE) $(BACKEND)

docker-run: env-check ## Run the backend image on port 8000 using backend/.env
	docker run -d --rm --name $(IMAGE) -p $(API_PORT):8000 --env-file $(BACKEND)/.env $(IMAGE)
	@echo "API → $(API_URL)  (stop with: make docker-stop)"

docker-stop: ## Stop the running backend container
	-docker stop $(IMAGE)

# --- Deploy ------------------------------------------------------------------

deploy-api: ## Deploy backend to Fly.io (needs flyctl + `fly secrets set GOOGLE_MAPS_API_KEY=...`)
	cd $(BACKEND) && fly deploy

deploy-web: ## Deploy frontend to Vercel production
	cd $(FRONTEND) && npx vercel --prod

# --- Housekeeping ------------------------------------------------------------

clean: ## Remove venv and Python caches
	rm -rf $(VENV)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
