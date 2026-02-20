---
title: Enabling CinderX in a Django dummy service
---

# Enabling CinderX in a Django dummy service

This tutorial walks through a concrete, minimal Django service flow you can run locally in minutes.
It is designed to keep CinderX runtime identity explicit and to avoid accidental headline claims from
non-publishable runs.

## Goal

- Build a tiny Django app with a real endpoint (`/health/`)
- Validate app behavior under local CPython
- Validate CinderX runtime identity (when available)
- Capture a repeatable request-loop measurement shape

## Step 1: create the dummy app

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python django
.venv/bin/django-admin startproject dummy_service
```

## Step 2: add a minimal endpoint

```bash
cd dummy_service
cat > dummy_service/views.py <<'PY'
from django.http import JsonResponse

def health(_request):
    return JsonResponse({"status": "ok", "service": "dummy_service"})
PY

cat > dummy_service/urls.py <<'PY'
from django.contrib import admin
from django.urls import path

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
]
PY
```

## Step 3: run sanity tests (CPython path)

Use the exact interpreter path for this project:

```bash
PY_BIN="$(cd .. && pwd)/.venv/bin/python"
"$PY_BIN" manage.py test
```

Expected shape:

- `Found 0 test(s).`
- `System check identified no issues`

## Step 4: verify endpoint and run a request loop

Start server:

```bash
PY_BIN="$(cd .. && pwd)/.venv/bin/python"
"$PY_BIN" manage.py runserver 127.0.0.1:8010
```

In a second shell:

```bash
curl -sS http://127.0.0.1:8010/health/
```

Expected response:

```json
{ "status": "ok", "service": "dummy_service" }
```

Quick local request loop (shape check, not a publish claim):

```bash
PY_BIN="$(cd .. && pwd)/.venv/bin/python"
"$PY_BIN" ../scripts/tutorials/http_request_loop.py \
  --url http://127.0.0.1:8010/health/ \
  --count 50
```

## Step 5: verify CinderX runtime identity (required for CinderX claims)

```bash
$CINDERX_PYTHON -c "import cinderx,sys; print(sys.executable); print(cinderx.__file__)"
```

If this fails, keep results labeled CPython diagnostics only.

## Step 6: run app checks with CinderX runtime (when available)

```bash
$CINDERX_PYTHON manage.py test
```

Use identical app config, dependency set, workload shape, and machine profile for comparisons.

## Step 7: report responsibly

- Mark results as exploratory unless CinderX baseline verification and reproducibility guardrails
  are satisfied.
- Avoid publishing broad claims from single-machine, single-endpoint runs.

## Validation snapshot (executed in this repo)

Executed on 2026-02-19 (macOS arm64):

- `uv venv --python 3.14 .venv`: `0.12s`
- `uv pip install --python .venv/bin/python django`: `0.97s`
- `.venv/bin/django-admin startproject dummy_service`: `1.13s`
- `"$PY_BIN" manage.py test`: `0.27s`
- 50-request loop command above: `0.07s` total (`~0.783ms` mean per request)

These numbers are local reference timings, not benchmark claims.
