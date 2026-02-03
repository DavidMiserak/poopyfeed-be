# PoopyFeed

<p align="center">
  <img src="static/images/favicon.svg" width="128" alt="PoopyFeed logo" />
</p>

<p align="center">
  <a href="https://github.com/DavidMiserak/poopyfeed/actions/workflows/test.yml">
    <img src="https://github.com/DavidMiserak/poopyfeed/actions/workflows/test.yml/badge.svg" alt="Tests" />
  </a>
  <a href="https://codecov.io/gh/DavidMiserak/poopyfeed">
    <img src="https://codecov.io/gh/DavidMiserak/poopyfeed/branch/main/graph/badge.svg" alt="codecov" />
  </a>
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+" />
  <img src="https://img.shields.io/badge/django-6.0-green.svg" alt="Django 6.0" />
  <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black" />
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" />
  </a>
</p>

A baby care tracking web application built with Django. PoopyFeed helps
parents and caregivers monitor feeding, diaper changes, and sleep patterns
for infants.

## Features

### Tracking

- **Feedings**: Track bottle (amount in oz) and breast (duration, side) feedings
- **Diapers**: Log wet, dirty, or both diaper changes
- **Naps**: Track sleep times

<p align="center">
  <img src="docs/images/feeding-log.png" width="200" alt="Feeding log showing breast and bottle feedings" />
  <img src="docs/images/diaper-log.png" width="200" alt="Diaper change log" />
  <img src="docs/images/nap-log.png" width="200" alt="Nap log" />
</p>

### Child Sharing

Share access to children with other accounts via invite links:

- **Co-parent role**: Full access to view, add, edit, and delete entries
- **Caregiver role**: Limited access to view and add entries only
- Invite links are reusable and can be deactivated/reactivated
- Only the child's owner can manage sharing settings

<p align="center">
  <img src="docs/images/share-1.png" width="200" alt="Share management page" />
  <img src="docs/images/share-2.png" width="200" alt="Share management page" />
</p>

<p align="center">
  <img src="docs/images/parent.png" width="200" alt="Child card - owner view" />
  <img src="docs/images/coparent.png" width="200" alt="Child card - co-parent view" />
  <img src="docs/images/caregiver.png" width="200" alt="Child card - caregiver view" />
</p>

### Other Features

- **Multi-Child Support**: Manage multiple children per account
- **Email Authentication**: Secure email-based login via django-allauth
- **Progressive Web App**: Install on your phone's home screen for quick access

### Planned

- **REST API**: Mobile app support via Django REST Framework + Djoser
- **Pumping**: Record pumping sessions and milk output
- **Temperature**: Record body temperature
- **Weight**: Monitor growth measurements
- **Medication**: Log medication administration

## Technology Stack

- **Backend**: Django 6.0 (Python web framework)
- **Database**: PostgreSQL (containers) or SQLite (local dev)
- **Frontend**: Django Templates with Bootstrap 5 (via crispy-forms)
- **PWA**: Service worker with offline support
- **Authentication**: django-allauth with email-based login
- **Containers**: Podman (or Docker)

## Requirements

### System Dependencies

- Python 3.13+ (3.14 recommended)
- PostgreSQL 14+ (for container/production deployment)
- Podman or Docker with compose support (for local container development)

### Python Dependencies

See `requirements.txt` for full list. Key packages:

- Django 6.0
- django-allauth (authentication)
- django-crispy-forms + crispy-bootstrap5 (forms)
- djangorestframework + djoser (REST API)
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

### Admin Panel

Access the admin panel at `http://localhost:8000/admin/` (requires superuser).

To create a superuser in containers:

```bash
podman compose exec web python manage.py createsuperuser
```

## Deployment

### Render (Recommended)

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
- `DJANGO_SECRET_KEY`: Secret key for cryptographic signing
- `DJANGO_DEBUG`: Set to `false` in production
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Contributing

When contributing to PoopyFeed:

1. Run `make pre-commit-setup` to install pre-commit hooks
2. Follow conventional commit format for all commits (enforced by hooks)
3. Run `pre-commit run --all-files` before committing
4. Ensure tests pass with `make test`

---

Built with ❤️ for keeping track of the little ones.
