# Containerfile
# Multi-stage build for Django application

# Stage 1: Base — shared dependencies and environment
FROM docker.io/python:3.13-slim-bullseye AS base

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY ./requirements.txt .
RUN pip install -r requirements.txt

# Stage 2: Development — runserver with full tooling
FROM base AS development

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Stage 3: Production — hardened with non-root user and gunicorn
FROM base AS production

ENV DJANGO_SETTINGS_MODULE=django_project.settings

RUN addgroup --system django && adduser --system --ingroup django django

COPY --chown=django:django . .
RUN python manage.py collectstatic --noinput

USER django

EXPOSE 8000
CMD ["gunicorn", "django_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
