FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-serving.txt .
RUN pip install --no-cache-dir -r requirements-serving.txt
COPY promotion_assistant ./promotion_assistant
COPY america ./america
RUN useradd --create-home app && mkdir -p /data && chown app:app /data
USER app
ENV POSTER_DATA_DIR=/data
EXPOSE 8081 50052
CMD ["python","-m","promotion_assistant","--host","0.0.0.0","--grpc-address","0.0.0.0:50052"]
