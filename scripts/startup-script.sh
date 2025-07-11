#!/bin/bash

# Elasticsearch startup script for Google Compute Engine
# This installs and configures Elasticsearch 8.11 for MVP use

set -e  # Exit on any error

echo "=== Starting Elasticsearch Installation ==="

# Update system
apt-get update -y
apt-get install -y wget curl gnupg apt-transport-https

# Install Java (required for Elasticsearch)
apt-get install -y openjdk-11-jdk

# Add Elasticsearch repository
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | apt-key add -
echo "deb https://artifacts.elastic.co/packages/8.x/apt stable main" | tee /etc/apt/sources.list.d/elastic-8.x.list

# Update package list and install Elasticsearch
apt-get update -y
apt-get install -y elasticsearch=8.11.4

# Format and mount the data disk
echo "=== Setting up data disk ==="
# Check if data disk exists and isn't mounted
if lsblk | grep -q "sdb" && ! mountpoint -q /var/lib/elasticsearch; then
    echo "Formatting data disk..."
    mkfs.ext4 -F /dev/sdb
    
    # Create mount point and mount
    mkdir -p /var/lib/elasticsearch
    mount /dev/sdb /var/lib/elasticsearch
    
    # Add to fstab for permanent mounting
    echo "/dev/sdb /var/lib/elasticsearch ext4 defaults 0 0" >> /etc/fstab
    
    # Set correct ownership
    chown -R elasticsearch:elasticsearch /var/lib/elasticsearch
    chmod 755 /var/lib/elasticsearch
fi

# Configure Elasticsearch
echo "=== Configuring Elasticsearch ==="

# Backup original config
cp /etc/elasticsearch/elasticsearch.yml /etc/elasticsearch/elasticsearch.yml.backup

# Create new configuration
cat > /etc/elasticsearch/elasticsearch.yml << 'EOF'
# Cluster name
cluster.name: customer-service-mvp

# Node name
node.name: node-1

# Data and logs paths
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch

# Network settings
network.host: 0.0.0.0
http.port: 9200
discovery.type: single-node

# Security settings (basic for MVP)
xpack.security.enabled: true
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false

# Performance settings for e2-standard-2
bootstrap.memory_lock: false
indices.memory.index_buffer_size: 512mb

# Disable machine learning (saves memory)
xpack.ml.enabled: false
EOF

# Set JVM heap size (half of available RAM = 4GB for e2-standard-2)
cat > /etc/elasticsearch/jvm.options.d/heap.options << 'EOF'
-Xms2g
-Xmx2g
EOF

# Create systemd override to increase file limits
mkdir -p /etc/systemd/system/elasticsearch.service.d
cat > /etc/systemd/system/elasticsearch.service.d/override.conf << 'EOF'
[Service]
LimitNOFILE=65535
LimitNPROC=4096
EOF

# Reload systemd and enable Elasticsearch
systemctl daemon-reload
systemctl enable elasticsearch

# Start Elasticsearch
echo "=== Starting Elasticsearch ==="
systemctl start elasticsearch

# Wait for Elasticsearch to start
echo "Waiting for Elasticsearch to start..."
for i in {1..30}; do
    if curl -s localhost:9200 > /dev/null; then
        echo "Elasticsearch is running!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 10
done

# Reset elastic user password and create a simple password
echo "=== Setting up authentication ==="
# Generate a simple password for MVP
ES_PASSWORD="mvp-elastic-2024"

# Reset the elastic user password
echo "y" | /usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic -i --password "${ES_PASSWORD}"

# Test the connection
echo "=== Testing Elasticsearch ==="
if curl -u "elastic:${ES_PASSWORD}" -X GET "localhost:9200" 2>/dev/null; then
    echo "SUCCESS: Elasticsearch is working with authentication"
else
    echo "ERROR: Elasticsearch authentication test failed"
fi

# Save credentials to a file for easy access
cat > /home/elasticsearch-credentials.txt << EOF
Elasticsearch MVP Credentials
============================
URL: http://$(curl -s ifconfig.me):9200
Username: elastic
Password: ${ES_PASSWORD}

Internal URL: http://localhost:9200

Test command:
curl -u "elastic:${ES_PASSWORD}" -X GET "http://localhost:9200"

For your Cloud Run service, use:
ELASTICSEARCH_URL=http://$(curl -s ifconfig.me):9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=${ES_PASSWORD}
ELASTICSEARCH_VERIFY_CERTS=false
EOF

echo "=== Installation Complete ==="
echo "Elasticsearch credentials saved to /home/elasticsearch-credentials.txt"
echo "External IP: $(curl -s ifconfig.me)"
echo "Service status:"
systemctl status elasticsearch --no-pager