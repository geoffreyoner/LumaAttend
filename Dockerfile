FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir Flask Werkzeug opencv-python-headless numpy

RUN mkdir -p instance models

EXPOSE 5000

CMD ["python", "app.py"]
