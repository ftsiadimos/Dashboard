FROM python:3.12-slim

WORKDIR /app

# install dependencies first so they can be cached
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy only the application code and resources that are needed at runtime
COPY app.py VERSION ./
COPY dashboard/ ./dashboard/
COPY templates/ ./templates/
COPY static/ ./static/

# data directory is created at runtime; just ensure icons subfolder exists
RUN mkdir -p dashboard/data/icons

EXPOSE 6008

CMD ["gunicorn", "--bind", "0.0.0.0:6008", "--workers", "2", "--access-logfile", "-", "app:create_app()"]
