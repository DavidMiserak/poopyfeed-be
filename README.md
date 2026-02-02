# PoopyFeed

A baby care tracking web application built with Django. PoopyFeed helps
parents and caregivers monitor feeding, diaper changes, and sleep patterns
for infants.

## Features

### Implemented

- **Feedings**: Track bottle (amount in oz) and breast (duration, side) feedings
- **Diapers**: Log wet, dirty, or both diaper changes
- **Naps**: Track sleep times
- **Multi-Child Support**: Manage multiple children per account

### Planned

- **Pumping**: Record pumping sessions and milk output
- **Temperature**: Record body temperature
- **Weight**: Monitor growth measurements
- **Medication**: Log medication administration
- **Multi-Caregiver Access**: Shared access for parents, family members, and babysitters
- **REST API**: Django REST Framework + Djoser (dependencies installed, not yet configured)
- **Payments**: Stripe integration (dependency installed, not yet configured)

## Screenshots

<p align="center">
  <img src="docs/images/child-card.jpeg" width="200" alt="Child profile card with activity summary">
  <img src="docs/images/diaper-log.jpeg" width="200" alt="Diaper change log">
  <img src="docs/images/nap-log.jpeg" width="200" alt="Nap log">
  <img src="docs/images/feeding-log.jpeg" width="200" alt="Feeding log showing breast and bottle feedings">
</p>

## Technology Stack

- **Backend**: Django 6.0 (Python web framework)
- **Database**: PostgreSQL (containers) or SQLite (local dev)
- **Frontend**: Django Templates with Bootstrap 5 (via crispy-forms)
- **Authentication**: django-allauth with email-based login
- **Containers**: Podman (or Docker)

## Requirements

### System Dependencies

- Python 3.13+
- PostgreSQL 14+ (for container-based development)
- Podman or Docker with compose support

### Python Dependencies

See `requirements.txt` for full list. Key packages:

- Django 6.0
- django-allauth (authentication)
- django-crispy-forms + crispy-bootstrap5 (forms)
- psycopg2-binary (PostgreSQL)
- whitenoise (static files)
- gunicorn (production server)

## Installation

### Container-Based Development (Recommended)

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd poopyfeed
   ```

2. Set up pre-commit hooks:

   ```bash
   make pre-commit-setup
   ```

3. Start the containers (web + PostgreSQL):

   ```bash
   make run
   ```

4. Run migrations:

   ```bash
   make migrate
   ```

5. Access the application at `http://localhost:8000`

Other useful commands:

```bash
make test             # Run tests
make logs             # View container logs
make stop             # Stop containers
```

### Local Development (without containers)

1. Create and activate virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run migrations and start server (uses SQLite):

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

3. Run a single test:

   ```bash
   python manage.py test accounts.tests.CustomUserTests.test_create_user
   ```

## Usage

1. Access the application at `http://localhost:8000`
2. Create an account or log in
3. Access the admin panel at `http://localhost:8000/admin/` (requires superuser)

To create a superuser in containers:

```bash
podman compose exec web python manage.py createsuperuser
```

## Self-Hosting

This application is designed for self-hosting with the following considerations:

- Configure HTTPS for production deployment
- Set up proper backup procedures for PostgreSQL database
- Configure reverse proxy (nginx/Apache) for production deployment
- Set environment variables for secrets (see `podman-compose.yaml` for reference)

## Contributing

When contributing to PoopyFeed:

1. Run `make pre-commit-setup` to install pre-commit hooks
2. Follow conventional commit format for all commits (enforced by hooks)
3. Run `pre-commit run --all-files` before committing
4. Ensure tests pass with `make test`

## License

[Add your chosen license here]

---

Built with ❤️ for keeping track of the little ones.
