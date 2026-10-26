# Production build: compiled React served by FastAPI at the same origin.
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
RUN npm install --no-audit --no-fund
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /build/dist ./web
ENV FRONTEND_DIST=/app/web PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
