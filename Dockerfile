FROM python:3.12-slim

WORKDIR /app

# 依存インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ配置
COPY app ./app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
