---
title: Enabling CinderX in a Django dummy service
---

# Enabling CinderX in a Django dummy service

This tutorial provides a safe starter flow for trying CinderX with a minimal Django app.

## Goal

- Keep startup and test paths explicit.
- Verify runtime identity before making any performance claim.

## Step 1: create the dummy app

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python django
.venv/bin/django-admin startproject dummy_service
```

## Step 2: verify CinderX runtime path

```bash
$CINDERX_PYTHON -c "import cinderx,sys; print(sys.executable); print(cinderx.__file__)"
```

If this fails, keep the app on CPython until CinderX runtime is actually available.

## Step 3: run tests with both runtimes

```bash
cd dummy_service
python manage.py test
$CINDERX_PYTHON manage.py test
```

## Step 4: add simple request-path smoke

Use a minimal endpoint and run repeated local requests under each runtime with identical settings.
Record command lines, runtime versions, and host details.

## Step 5: report responsibly

- Mark results as exploratory unless CinderX baseline verification and reproducibility guardrails
  are satisfied.
- Avoid publishing broad claims from single-machine, single-endpoint runs.
