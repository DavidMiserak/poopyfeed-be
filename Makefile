# Makefile

RUNTIME := podman # podman or docker
REGISTRY := localhost
IMAGE_NAME := poopyfeed-be
IMAGE_TAG := latest

.PHONY: pre-commit-setup
pre-commit-setup:
	@echo "Setting up pre-commit hooks..."
	@echo "consider running <pre-commit autoupdate> to get the latest versions"
	pre-commit install
	pre-commit install --install-hooks
	pre-commit run --all-files

.PHONY: image-build-prod
image-build-prod: Containerfile
	$(RUNTIME) build --target production -t $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG) -f Containerfile .

.PHONY: image-build-dev
image-build-dev: Containerfile
	$(RUNTIME) build --target development -t $(REGISTRY)/$(IMAGE_NAME):dev -f Containerfile .

.PHONY: image-build
image-build: image-build-dev

.PHONY: stop
stop:
	$(RUNTIME) compose down

.PHONY: run
run: podman-compose.yaml image-build
	$(RUNTIME) compose down || true
	$(RUNTIME) compose -f $< up -d

.PHONY: test
test:
	$(RUNTIME) compose exec web coverage run manage.py test
	$(RUNTIME) compose exec web coverage report
	$(RUNTIME) compose exec web coverage xml

.PHONY: test-local
test-local:
	DJANGO_DEBUG=True coverage run manage.py test
	coverage report
	coverage xml

.PHONY: coverage-html
coverage-html: test
	$(RUNTIME) compose exec web coverage html
	@echo "Coverage report generated at htmlcov/index.html"

.PHONY: migrate
migrate:
	$(RUNTIME) compose exec web python manage.py makemigrations
	$(RUNTIME) compose exec web python manage.py migrate

.PHONY: logs
logs:
	sleep 2
	$(RUNTIME) compose logs

# Render deployment
.PHONY: render-build
render-build:
	pip install -r requirements.txt
	python manage.py collectstatic --no-input
	python manage.py migrate
