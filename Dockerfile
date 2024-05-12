FROM python:latest

ENV PYTHONUNBUFFERED 1
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN prisma generate

CMD python3 /app/main.py