# Traefik Integration Guide (Docker Only)

This directory contains Traefik configuration for **Docker-based deployments** with automatic SSL/TLS certificates and DNS-based routing.

> **⚠️ Important:** This Traefik integration is designed for **Docker and Docker Compose deployments only**.
>
> **For Kubernetes deployments**, use **ingress-nginx** instead. See [k8s/README.md](../k8s/README.md) for Kubernetes deployment guide.

## What is Traefik?

Traefik is a modern reverse proxy and load balancer that makes deploying microservices easy. It automatically:
- Generates SSL/TLS certificates from Let's Encrypt
- Routes requests based on domain names
- Handles HTTPS redirects
- Provides rate limiting
- Adds security headers
- Monitors services with health checks

## Features

- **Automatic SSL/TLS**: Free certificates from Let's Encrypt with auto-renewal
- **DNS-based Routing**: Route traffic to services based on subdomain
- **Security**: Built-in rate limiting, security headers, and basic auth
- **Monitoring**: Traefik dashboard with real-time metrics
- **Zero-downtime**: Automatic service discovery and health checks

## Prerequisites

1. **Domain Name**: You need a domain pointing to your server
2. **DNS Records**: Configure A/AAAA records:
   ```
   api.example.com     → Your server IP
   traefik.example.com → Your server IP
   db.example.com      → Your server IP (optional)
   minio.example.com   → Your server IP (optional)
   s3.example.com      → Your server IP (optional)
   flower.example.com  → Your server IP (optional)
   ```
3. **Open Ports**: Ports 80 (HTTP) and 443 (HTTPS) must be accessible from the internet
4. **Valid Email**: For Let's Encrypt certificate expiry notifications

## Quick Start

### 1. Configure Domain

```bash
# Copy environment template
cp traefik/.env.example traefik/.env

# Edit configuration
nano traefik/.env
```

Update these values:
```env
DOMAIN=yourdomain.com
ACME_EMAIL=your-email@example.com
```

### 2. Update Traefik Configuration

Edit `traefik/traefik.yml` and update:
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com  # Change this!
```

### 3. Start with Traefik

```bash
# Start all services with Traefik
docker-compose -f docker-compose.yml -f docker-compose.traefik.yml up -d

# View logs
docker-compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f traefik

# Check certificate generation
docker-compose -f docker-compose.yml -f docker-compose.traefik.yml exec traefik cat /certificates/acme.json
```

### 4. Access Your Services

Once running, access your services via HTTPS:

- **API**: https://api.yourdomain.com
- **API Docs**: https://api.yourdomain.com/docs
- **Traefik Dashboard**: https://traefik.yourdomain.com (requires basic auth)
- **Database UI**: https://db.yourdomain.com (optional, requires basic auth)
- **MinIO Console**: https://minio.yourdomain.com
- **MinIO API**: https://s3.yourdomain.com
- **Flower**: https://flower.yourdomain.com (requires basic auth)

## DNS Challenge (For Wildcard Certificates)

If you want wildcard certificates (*.example.com) or your server is behind a firewall, use DNS challenge with Cloudflare:

### 1. Get Cloudflare API Key

1. Login to Cloudflare
2. Go to My Profile → API Tokens
3. Create Token or use Global API Key
4. Copy the API key

### 2. Configure DNS Challenge

Update `traefik/.env`:
```env
CF_API_EMAIL=your-cloudflare-email@example.com
CF_API_KEY=your-cloudflare-global-api-key
```

Update `traefik/traefik.yml`:
```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com
      storage: /certificates/acme.json
      dnsChallenge:
        provider: cloudflare
        delayBeforeCheck: 30
        resolvers:
          - "1.1.1.1:53"
          - "8.8.8.8:53"
```

Comment out the `httpChallenge` section.

## Troubleshooting

### Certificate Generation Issues

1. **Check Traefik logs**:
   ```bash
   docker-compose logs traefik
   ```

2. **Verify DNS records**:
   ```bash
   nslookup api.yourdomain.com
   ```

3. **Test with Let's Encrypt staging** (avoid rate limits):
   Update `traefik/traefik.yml`:
   ```yaml
   certificatesResolvers:
     letsencrypt:
       acme:
         caServer: https://acme-staging-v02.api.letsencrypt.org/directory
   ```

4. **Check certificate file**:
   ```bash
   docker exec saas_traefik cat /certificates/acme.json
   ```

### Port Conflicts

If ports 80 or 443 are in use:
```bash
# Check what's using the ports
sudo lsof -i :80
sudo lsof -i :443

# Stop conflicting services
sudo systemctl stop nginx  # or apache2
```

### Dashboard Not Accessible

1. Check basic auth credentials (default: admin/changeme)
2. Generate new password hash:
   ```bash
   # Install apache2-utils
   sudo apt-get install apache2-utils

   # Generate hash
   echo $(htpasswd -nb admin yourpassword) | sed -e s/\\$/\\$\\$/g
   ```
3. Update `docker-compose.traefik.yml` with new hash

### Service Not Reachable

1. Check service labels:
   ```bash
   docker inspect saas_api | grep traefik
   ```

2. Verify Traefik can reach the service:
   ```bash
   docker exec saas_traefik ping api
   ```

3. Check Traefik dashboard for service status

## Security Best Practices

### 1. Change Default Passwords

Update basic auth password for Traefik dashboard and other services:
```bash
htpasswd -nb admin YourStrongPassword | sed -e s/\\$/\\$\\$/g
```

### 2. Restrict Dashboard Access

Add IP whitelist in `traefik/dynamic/middleware.yml`:
```yaml
http:
  middlewares:
    admin-whitelist:
      ipWhiteList:
        sourceRange:
          - "YOUR_IP/32"
```

Then update `docker-compose.traefik.yml`:
```yaml
- "traefik.http.routers.traefik.middlewares=auth,admin-whitelist"
```

### 3. Use Strong Rate Limits

Apply strict rate limiting to public endpoints:
```yaml
- "traefik.http.routers.api.middlewares=rate-limit-strict"
```

### 4. Monitor Certificate Expiry

Set up monitoring for certificate expiry (Let's Encrypt certs expire in 90 days):
- Traefik auto-renews 30 days before expiry
- Check logs regularly: `docker-compose logs traefik | grep certificate`

## Kubernetes Deployment

**Traefik is not used for Kubernetes deployments in this framework.**

For Kubernetes, use **ingress-nginx** with **cert-manager** instead:

```bash
# Install ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Deploy application with ingress
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/cert-issuer.yaml
```

See the [Kubernetes Guide](../k8s/README.md) for complete deployment instructions.

## Additional Resources

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Let's Encrypt Rate Limits](https://letsencrypt.org/docs/rate-limits/)
- [DNS Challenge Providers](https://doc.traefik.io/traefik/https/acme/#providers)
- [Traefik Middlewares](https://doc.traefik.io/traefik/middlewares/overview/)

## File Structure

```
traefik/
├── traefik.yml              # Main Traefik configuration
├── dynamic/
│   └── middleware.yml       # Dynamic middleware configuration
├── .env.example             # Environment template
└── README.md               # This file

docker-compose.traefik.yml  # Traefik override for docker-compose
```

## Support

For issues or questions:
1. Check Traefik logs: `docker-compose logs traefik`
2. Review Traefik dashboard: https://traefik.yourdomain.com
3. Consult [Traefik Community Forum](https://community.traefik.io/)
