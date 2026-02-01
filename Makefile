# Makefile

RUNTIME := podman # podman or docker

.PHONY: pre-commit-setup
pre-commit-setup:
	@echo "Setting up pre-commit hooks..."
	@echo "consider running <pre-commit autoupdate> to get the latest versions"
	pre-commit install
	pre-commit install --install-hooks
	pre-commit run --all-files

.PHONY: stop
stop:
	$(RUNTIME) compose down

.PHONY: run
run:
	$(RUNTIME) compose down || true
	$(RUNTIME) compose up --build -d

.PHONY: test
test:
	$(RUNTIME) compose exec web python manage.py test

.PHONY: migrate
migrate:
	$(RUNTIME) compose exec web python manage.py makemigrations
	$(RUNTIME) compose exec web python manage.py migrate

.PHONY: logs
logs:
	sleep 2
	$(RUNTIME) compose logs

.PHONY: stripe-listen
stripe-listen:
	stripe listen --forward-to localhost:8000/webhooks/stripe/
