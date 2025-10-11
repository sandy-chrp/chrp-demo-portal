
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

COPY . .

RUN mkdir -p /app/static /appp/media /app/staticfiles

RUN python manage.py makemigrations

RUN python manage.py migrate

RUN python manage.py collectstatic --noinput


CMD ["gunicorn", "demo_portal.wsgi:application", "--bind", "0.0.0.0:8000"]