FROM python:3.11-slim

WORKDIR /app

# Copy both directories
COPY customer_service/ ./customer_service/
COPY admin_api/ ./admin_api/

# Install dependencies
RUN pip install -r admin_api/requirements.txt

# Set working directory to admin_api
WORKDIR /app/admin_api

# Add parent directory to Python path so imports work
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]