FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY knowledge ./knowledge
RUN useradd --uid 10001 --create-home alia && mkdir -p /data && chown alia:alia /data
COPY entrypoint.py ./entrypoint.py
ENV DATA_DIR=/data
CMD ["python", "entrypoint.py"]
