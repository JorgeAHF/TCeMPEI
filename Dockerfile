FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV DASH_DEBUG_MODE=False
ENV DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/tcempei

CMD ["python", "app/main.py"]
