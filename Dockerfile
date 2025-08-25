# Trading Optimization Platform Dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy Python requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend package files and install dependencies
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci

# Copy application code
COPY . .

# Build frontend
RUN cd frontend && npm run build

# Create demo data directories
RUN mkdir -p demo_data/simulated demo_data/delayed

# Initialize database
RUN python -c "from trading_platform.database.database import init_database; init_database()"

# Expose ports
EXPOSE 8000 3000

# Set environment variables
ENV PYTHONPATH=/app
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV DATABASE_URL=sqlite:///./trading_platform.db

# Create startup script
RUN echo '#!/bin/bash\n\
# Start monitoring in background\n\
python -c "\n\
import asyncio\n\
from trading_platform.services.monitoring.health_monitor import health_monitor\n\
from trading_platform.services.monitoring.alert_manager import get_alert_manager\n\
from trading_platform.services.monitoring.metrics_collector import metrics_collector\n\
\n\
async def start_monitoring():\n\
    await health_monitor.start_monitoring()\n\
    alert_mgr = get_alert_manager(health_monitor, metrics_collector)\n\
    await alert_mgr.start_monitoring()\n\
    print(\"Monitoring services started\")\n\
    while True:\n\
        await asyncio.sleep(60)\n\
\n\
asyncio.run(start_monitoring())\n\
" &\n\
\n\
# Start the FastAPI server\n\
exec python -m uvicorn trading_platform.api.main:app --host 0.0.0.0 --port 8000\n\
' > /app/start_container.sh && chmod +x /app/start_container.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start the application
CMD ["/app/start_container.sh"]