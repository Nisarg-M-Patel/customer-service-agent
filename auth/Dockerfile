FROM python:3.11-slim

# Install Terraform
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip \
    && unzip terraform_1.6.0_linux_amd64.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform_1.6.0_linux_amd64.zip \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]