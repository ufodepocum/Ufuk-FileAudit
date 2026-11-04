FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/ufuk-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ufuk-requirements.txt
COPY app /app
RUN useradd --uid 10001 --no-create-home app && mkdir -p public && DJANGO_SECRET_KEY=build python manage.py makemigrations --check --dry-run && DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput && chown -R app:app /app
USER 10001
CMD ["sh","-c","python manage.py migrate --noinput && python bootstrap.py && python manage.py purge_audit && exec gunicorn AuditSphere.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 300 --access-logfile - --error-logfile -"]
