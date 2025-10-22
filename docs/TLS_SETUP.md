# TLS/SSL Certificate Setup Guide

This guide covers setting up TLS certificates for secure HTTPS communication.

## Table of Contents

1. [Kubernetes with cert-manager (Automated)](#kubernetes-cert-manager)
2. [Manual Certificate Setup](#manual-certificates)
3. [Local Development with Self-Signed Certificates](#local-development)
4. [Production Best Practices](#production-best-practices)

## Kubernetes with cert-manager (Automated)

### Prerequisites

- Kubernetes cluster
- kubectl configured
- Domain name pointing to your cluster

### 1. Install cert-manager

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Verify installation
kubectl get pods --namespace cert-manager
```

### 2. Create ClusterIssuer

```bash
# Apply the certificate issuer
kubectl apply -f k8s/cert-issuer.yaml
```

The issuer configuration:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com  # Change this!
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

### 3. Update Ingress

The ingress configuration automatically requests certificates:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: saas-backend-tls
```

### 4. Verify Certificate

```bash
# Check certificate status
kubectl describe certificate saas-backend-tls -n saas-backend

# Should show: Status: True, Type: Ready

# Test HTTPS
curl https://api.yourdomain.com/health
```

## Manual Certificates

### Using Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone \
  -d api.yourdomain.com \
  -d flower.yourdomain.com \
  --email your-email@example.com \
  --agree-tos

# Certificates location:
# /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/api.yourdomain.com/privkey.pem
```

### Using Custom CA Certificate

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate CSR
openssl req -new -key server.key -out server.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=api.yourdomain.com"

# Get certificate from your CA
# Then combine with intermediate certificates:
cat server.crt intermediate.crt > fullchain.pem
```

### Create Kubernetes Secret

```bash
# Create TLS secret from certificate files
kubectl create secret tls saas-backend-tls \
  --cert=/path/to/fullchain.pem \
  --key=/path/to/privkey.pem \
  --namespace=saas-backend
```

## Local Development

### Self-Signed Certificate

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem \
  -out cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Run Uvicorn with TLS

```bash
# Start server with TLS
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile=key.pem \
  --ssl-certfile=cert.pem
```

### Using mkcert for Trusted Local Certificates

```bash
# Install mkcert
brew install mkcert  # macOS
# or
sudo apt install mkcert  # Linux

# Install local CA
mkcert -install

# Generate certificate
mkcert localhost 127.0.0.1 ::1

# Run server
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8443 \
  --ssl-keyfile=localhost+2-key.pem \
  --ssl-certfile=localhost+2.pem
```

## Production Best Practices

### 1. Certificate Management

- ✅ Use automated certificate renewal (cert-manager)
- ✅ Set up monitoring for certificate expiration
- ✅ Keep private keys secure (use secrets management)
- ✅ Use 2048-bit or 4096-bit RSA keys
- ✅ Enable OCSP stapling
- ✅ Implement certificate pinning (optional)

### 2. TLS Configuration

#### Strong Cipher Suites

```nginx
# Nginx configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers on;
```

#### Kubernetes Ingress Annotations

```yaml
annotations:
  nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.2 TLSv1.3"
  nginx.ingress.kubernetes.io/ssl-ciphers: "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256"
  nginx.ingress.kubernetes.io/ssl-prefer-server-ciphers: "true"
```

### 3. HSTS (HTTP Strict Transport Security)

```yaml
# Ingress annotation
nginx.ingress.kubernetes.io/configuration-snippet: |
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### 4. Certificate Monitoring

```bash
# Check certificate expiration
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com </dev/null 2>/dev/null | \
  openssl x509 -noout -dates

# Automated monitoring with kubectl
kubectl get certificate -n saas-backend -w
```

### 5. Backup Certificates

```bash
# Backup TLS secret
kubectl get secret saas-backend-tls -n saas-backend -o yaml > tls-backup.yaml

# Restore if needed
kubectl apply -f tls-backup.yaml
```

## Troubleshooting

### Certificate Not Ready

```bash
# Check certificate status
kubectl describe certificate saas-backend-tls -n saas-backend

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Check ingress events
kubectl describe ingress saas-backend-ingress -n saas-backend
```

### Common Issues

#### 1. DNS Not Propagated

```bash
# Check DNS
dig api.yourdomain.com
nslookup api.yourdomain.com

# Wait for DNS propagation (can take up to 48 hours)
```

#### 2. HTTP-01 Challenge Failed

```bash
# Ensure port 80 is accessible
curl http://api.yourdomain.com/.well-known/acme-challenge/test

# Check ingress class
kubectl get ingressclass
```

#### 3. Rate Limiting

Let's Encrypt has rate limits:
- 50 certificates per registered domain per week
- Use staging environment for testing

```yaml
# Use staging issuer for testing
cert-manager.io/cluster-issuer: "letsencrypt-staging"
```

### Testing TLS Configuration

```bash
# Test with OpenSSL
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com

# Test with curl
curl -vI https://api.yourdomain.com

# SSL Labs test (comprehensive)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=api.yourdomain.com
```

## Renewal

### Automatic Renewal (cert-manager)

cert-manager automatically renews certificates 30 days before expiration.

```bash
# Force renewal
kubectl delete certificate saas-backend-tls -n saas-backend
# Certificate will be automatically recreated
```

### Manual Renewal (certbot)

```bash
# Dry run
sudo certbot renew --dry-run

# Actual renewal
sudo certbot renew

# Restart services
sudo systemctl reload nginx
```

## Security Headers

Add these security headers for enhanced TLS security:

```yaml
# Ingress annotations
nginx.ingress.kubernetes.io/configuration-snippet: |
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header X-XSS-Protection "1; mode=block" always;
```

## Monitoring Certificate Expiration

### Prometheus Alert

```yaml
- alert: CertificateExpiringSoon
  expr: certmanager_certificate_expiration_timestamp_seconds - time() < 7*24*60*60
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Certificate {{ $labels.name }} expiring soon"
```

### Custom Script

```bash
#!/bin/bash
# check-cert-expiry.sh

DOMAIN="api.yourdomain.com"
DAYS_WARNING=30

EXPIRY=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | \
  openssl x509 -noout -enddate | cut -d= -f2)

EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

if [ $DAYS_LEFT -lt $DAYS_WARNING ]; then
  echo "WARNING: Certificate expires in $DAYS_LEFT days"
  exit 1
fi

echo "Certificate valid for $DAYS_LEFT days"
```

## References

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [SSL Labs Testing Tool](https://www.ssllabs.com/ssltest/)
