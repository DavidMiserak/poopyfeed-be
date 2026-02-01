# PoopyFeed

A comprehensive baby care tracking web application built with
Django. PoopyFeed helps parents and caregivers monitor feeding, diaper
changes, sleep patterns, and health metrics for infants.

## Features

### Core Tracking

- **Bottle Feeding**: Track breast milk and formula consumption with timestamps and amounts
- **Breastfeeding**: Monitor left/right breast sessions with duration tracking
- **Pumping**: Record pumping sessions and milk output
- **Diapers**: Log poop and pee occurrences with notes
- **Naps**: Track sleep duration and patterns
- **Temperature**: Record body temperature in Fahrenheit
- **Weight**: Monitor growth with weight measurements
- **Medication**: Log medication administration with dosages and times

### Planned Features

- **Multi-Caregiver Access**: Shared access for parents, family members, and babysitters
- **Push Notifications**: Automatic reminders for feeding, medication, and care activities
- **PWA Support**: Install as a Progressive Web App for offline access

## Technology Stack

- **Backend**: Django 6.0 (Python web framework)
- **Database**: PostgreSQL (containers) or SQLite (local dev)
- **Frontend**: Django Templates with Bootstrap 5 (via crispy-forms)
- **Authentication**: django-allauth with email-based login
- **API**: Django REST Framework + Djoser
- **Payments**: Stripe
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
- djangorestframework + djoser (API)
- django-crispy-forms + crispy-bootstrap5 (forms)
- stripe (payments)
- environs (environment configuration)
- psycopg2-binary (PostgreSQL)

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
make stripe-listen    # Forward Stripe webhooks locally
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
