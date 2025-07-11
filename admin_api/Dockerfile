FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY admin_api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Set Python path so imports work
ENV PYTHONPATH=/app

# Use Cloud Run's PORT environment variable
EXPOSE 8080

# Run the admin API
CMD ["uvicorn", "admin_api.main:app", "--host", "0.0.0.0", "--port", "8080"]