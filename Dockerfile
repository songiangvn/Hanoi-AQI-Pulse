FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/dashboard/requirements.txt

COPY . /app

EXPOSE 7860

CMD ["shiny", "run", "dashboard/app.py", "--host", "0.0.0.0", "--port", "7860"]
