# PoopyFeed Backend

<p align="center">
  <img src="static/images/favicon.svg" width="128" alt="PoopyFeed logo" />
</p>

<p align="center">
  <a href="https://github.com/DavidMiserak/poopyfeed-be/actions/workflows/test.yml">
    <img src="https://github.com/DavidMiserak/poopyfeed-be/actions/workflows/test.yml/badge.svg" alt="Tests" />
  </a>
  <a href="https://codecov.io/gh/DavidMiserak/poopyfeed-be">
    <img src="https://codecov.io/gh/DavidMiserak/poopyfeed-be/branch/main/graph/badge.svg" alt="codecov" />
  </a>
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+" />
  <img src="https://img.shields.io/badge/django-6.0-green.svg" alt="Django 6.0" />
  <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black" />
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" />
  </a>
  <a href="https://www.conventionalcommits.org/">
    <img src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits" alt="Conventional Commits" />
  </a>
</p>

A baby care tracking web application built with Django. PoopyFeed helps
parents and caregivers monitor feeding, diaper changes, and sleep patterns
for infants.

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Deployment](#deployment)
- [Contributing](#contributing)

## Features

### Tracking

- **Feedings**: Track bottle (amount in oz) and breast (duration, side) feedings with custom per-child bottle presets
- **Diapers**: Log wet, dirty, or both diaper changes
- **Naps**: Track sleep times
- **Batch Entry**: Log multiple past events at once via catch-up mode

<p align="center">
  <img src="docs/images/feeding-log.png" width="200" alt="Feeding log showing breast and bottle feedings" />
  <img src="docs/images/diaper-log.png" width="200" alt="Diaper change log" />
  <img src="docs/images/nap-log.png" width="200" alt="Nap log" />
</p>

### Analytics & Export

- **Feeding Trends**: Daily aggregates with configurable time range (1–90 days)
- **Diaper Patterns**: Wet/dirty distribution analysis
- **Sleep Summary**: Nap duration and frequency insights
- **Today & Weekly Summaries**: At-a-glance dashboards
- **Timeline**: Merged chronological activity feed across all tracking types
- **CSV Export**: Immediate download of tracking data
- **PDF Export**: Async generation via Celery with progress polling

### Child Sharing

Share access to children with other accounts via invite links:

- **Co-parent role**: Full access to view, add, edit, and delete entries
- **Caregiver role**: Limited access to view and add entries only
- Invite links are reusable and can be deactivated/reactivated
- Only the child's owner can manage sharing settings

<p align="center">
  <img src="docs/images/sharing.png" width="200" alt="Share management page" />
</p>

<p align="center">
  <img src="docs/images/child-list-parent.png" width="200" alt="Child card - owner view" />
  <img src="docs/images/child-list-coparent.png" width="200" alt="Child card - co-parent view" />
  <img src="docs/images/child-list-caregiver.png" width="200" alt="Child card - caregiver view" />
</p>

### Notifications

- **In-app notifications**: Alerts when other users log feedings, diapers, or naps for shared children
- **Feeding reminders**: Configurable interval-based reminders (2/3/4/6 hours) that bypass quiet hours
- **Quiet hours**: Per-user schedule to suppress non-critical notifications
- **Per-child preferences**: Toggle notification types (feedings, diapers, naps) per child

### Other Features

- **Multi-Child Support**: Manage multiple children per account
- **Email Authentication**: Secure email-based login via django-allauth (headless mode for SPA)
- **Progressive Web App**: Install on your phone's home screen for quick access
- **REST API**: Token-authenticated API at `/api/v1/` via Django REST Framework
- **Redis Caching**: Analytics and child access queries cached with automatic invalidation
- **Background Tasks**: Celery worker for PDF export and scheduled notification tasks

### Planned

- **Pumping**: Record pumping sessions and milk output
- **Temperature**: Record body temperature
- **Weight**: Monitor growth measurements
- **Medication**: Log medication administration

## Technology Stack

- **Backend**: Django 6.0 (Python web framework)
- **Database**: PostgreSQL (containers/production) or SQLite (local dev)
- **Cache & Sessions**: Redis 7
- **Task Queue**: Celery with Redis broker (PDF export, notifications, scheduled tasks)
- **Frontend**: Django Templates with Bootstrap 5 (via crispy-forms)
- **SPA Frontend**: Angular 21 (separate submodule, connects via REST API)
- **PWA**: Service worker with offline support
- **Authentication**: django-allauth with email-based login (headless mode for SPA)
- **Containers**: Podman (or Docker)

## Requirements

### System Dependencies

- Python 3.13+
- PostgreSQL 14+ (for container/production deployment)
- Redis 7+ (for caching, sessions, and Celery)
- Podman or Docker with compose support (for local container development)

### Python Dependencies

See `requirements.txt` for full list. Key packages:

- Django 6.0
- django-allauth (authentication)
- django-crispy-forms + crispy-bootstrap5 (forms)
- djangorestframework (REST API)
- celery + django-redis (background tasks, caching)
- reportlab + matplotlib (PDF export with charts)
- psycopg2-binary (PostgreSQL)
- whitenoise (static files)
- gunicorn (production server)

## Installation

### Container-Based Development (Recommended)

1. Clone the repository:

   ```bash
   git clone https://github.com/DavidMiserak/poopyfeed-be.git
   cd poopyfeed-be
   ```

2. Set up pre-commit hooks:

   ```bash
   make pre-commit-setup
   ```

3. Start the containers (web + PostgreSQL + Redis):

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
make test                          # Run tests with coverage
make test-backend-parallel-fast    # Fast parallel tests (~13-15s)
make logs                          # View container logs
make stop                          # Stop containers
make celery-worker                 # Start Celery worker (for PDF export)
make celery-beat                   # Start Celery beat (for feeding reminders)
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

3. Run tests:

   ```bash
   make test-local                # Full suite with coverage (~25-35s)
   python manage.py test accounts.tests.CustomUserTests.test_create_user  # Single test
   ```

When running locally without Redis, caching degrades gracefully and sessions use database storage.

## Usage

1. Access the application at `http://localhost:8000`
2. Create an account or log in
3. Add a child from the main page
4. Start logging feedings, diapers, and naps

### Install on Mobile

PoopyFeed is a Progressive Web App (PWA) that can be installed on your phone:

**Android (Chrome):**

1. Visit the site in Chrome
2. Tap the 3-dot menu → "Install app" or "Add to Home screen"
3. The app will appear on your home screen

**iOS (Safari):**

1. Visit the site in Safari
2. Tap the Share button → "Add to Home Screen"
3. The app will appear on your home screen

Once installed, the app launches in full-screen mode without browser chrome.

### Sharing Access with Others

To share a child's profile with a partner, family member, or caregiver:

1. From the child list, click **Share** on the child you want to share
2. Select a role:
   - **Co-parent**: Full access (view, add, edit, delete)
   - **Caregiver**: Limited access (view, add only)
3. Click **Create Invite Link**
4. Copy the link and send it to the person you want to share with
5. They click the link while logged into their account to gain access

To revoke access, return to the Share page and click **Remove** next to the user.

### REST API

The backend exposes a full REST API at `/api/v1/` for the Angular SPA frontend:

- **Children**: `/api/v1/children/` — CRUD with role-based access
- **Tracking**: `/api/v1/children/{id}/feedings/`, `diapers/`, `naps/` — nested CRUD
- **Batch**: `/api/v1/children/{id}/batch/` — bulk create up to 20 events
- **Analytics**: `/api/v1/analytics/children/{id}/feeding-trends/`, `diaper-patterns/`, `sleep-summary/`, `today-summary/`, `weekly-summary/`
- **Export**: CSV (synchronous) and PDF (async via Celery with status polling)
- **Timeline**: `/api/v1/analytics/children/{id}/timeline/` — merged activity feed
- **Notifications**: List, mark read, preferences, quiet hours, unread count
- **Auth**: django-allauth headless endpoints at `/api/v1/browser/v1/auth/`

Authentication: Token or Session. Rate limited (1000/hour default, stricter for invites and tracking creation).

### Admin Panel

Access the admin panel at `http://localhost:8000/admin/` (requires superuser).

To create a superuser in containers:

```bash
podman compose exec web python manage.py createsuperuser
```

## Deployment

### Official Docker Image

PoopyFeed is available as an official Docker image on Docker Hub:

```text
docker.io/davidmiserak/poopyfeed-be:latest
```

Use this image with Docker Compose, Podman Compose, or Quadlet for easy deployment.

### Quadlet (systemd)

Deploy PoopyFeed as systemd services using Podman Quadlet:

1. Copy quadlet files to your systemd user directory:

   ```bash
   mkdir -p ~/.config/containers/systemd/
   cp quadlet/* ~/.config/containers/systemd/
   ```

2. Update environment variables in `poopyfeed-web.container`:
   - Set `DJANGO_SECRET_KEY` to a secure random value
   - Set `DJANGO_DEBUG=False` for production
   - Update `DJANGO_ALLOWED_HOSTS` with your domain
   - Configure database credentials

3. Reload systemd and start services:

   ```bash
   systemctl --user daemon-reload
   systemctl --user start poopyfeed-web.service
   systemctl --user enable poopyfeed-web.service
   ```

4. Access at `http://localhost:8000` or configure a reverse proxy

The Quadlet setup includes:

- `poopyfeed-web.container` - Django web service
- `poopyfeed-db.container` - PostgreSQL database
- `poopyfeed-migrate.container` - Automatic migrations on startup
- `poopyfeed.network` - Container network
- `postgres_data.volume` - Persistent database storage

### Render (Cloud Hosting)

Deploy to [Render](https://render.com) using the included `render.yaml` Blueprint:

1. Fork this repository to your GitHub account
2. Create a new Render account and connect your GitHub
3. Click "New" > "Blueprint" and select your forked repository
4. Render will automatically provision:
   - A PostgreSQL database (free tier)
   - A Python web service running gunicorn
   - Auto-generated `DJANGO_SECRET_KEY`
5. After deployment, create a superuser via the Render shell:

   ```bash
   python manage.py createsuperuser
   ```

Required environment variables are configured automatically by the Blueprint.

### Self-Hosting

For self-hosting on your own infrastructure:

- Configure HTTPS for production deployment
- Set up proper backup procedures for PostgreSQL database
- Configure reverse proxy (nginx/Apache) for production deployment
- Set environment variables for secrets (see `podman-compose.yaml` for reference)

Required environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string (caching, sessions, Celery)
- `DJANGO_SECRET_KEY`: Secret key for cryptographic signing
- `DJANGO_DEBUG`: Set to `false` in production
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Contributing

When contributing to PoopyFeed:

1. Run `make pre-commit-setup` to install pre-commit hooks
2. Follow [conventional commit](https://www.conventionalcommits.org/) format for all commits (enforced by hooks)
3. Run `pre-commit run --all-files` before committing
4. Ensure tests pass with `make test` (98% coverage, 555+ tests)

---

Built with ❤️ for keeping track of the little ones.
