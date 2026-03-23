# Phase 1: Build React Frontend
FROM node:20-alpine AS build-stage
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Phase 2: Python Backend
FROM python:3.11-slim
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . .
# Copy static files from build stage to backend static folder
COPY --from=build-stage /app/frontend/dist ./static

# Expose port (FastAPI default)
EXPOSE 8000

# Metadata
ENV AWS_REGION=us-east-1
ENV PORT=8000

# "docker run -p 80:8000 astrovoice"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
