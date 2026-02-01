# Build stage for React frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/web

# Copy package files
COPY web/package*.json ./

# Install dependencies
RUN npm ci

# Copy source and build
COPY web/ ./
RUN npm run build

# Python application stage
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/web/dist ./web/dist

# Create data directory for SQLite databases
RUN mkdir -p /app/data

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
