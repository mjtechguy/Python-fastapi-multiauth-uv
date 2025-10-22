# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the SaaS Backend Framework.

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- cert-manager installed (for TLS certificates)
- nginx-ingress-controller installed
- Optional: External PostgreSQL and Redis instances

## Quick Start

### 1. Install cert-manager (if not already installed)

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

### 2. Update Configuration

Edit the following files with your actual values:

- `secret.yaml` - Database credentials, API keys, etc.
- `ingress.yaml` - Your domain names
- `cert-issuer.yaml` - Your email address

### 3. Deploy

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Create TLS certificate issuers
kubectl apply -f cert-issuer.yaml

# Create ConfigMap and Secrets
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml

# Deploy application
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Enable autoscaling
kubectl apply -f hpa.yaml
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n saas-backend

# Check services
kubectl get svc -n saas-backend

# Check ingress
kubectl get ingress -n saas-backend

# Check TLS certificate
kubectl get certificate -n saas-backend
```

## Helm Deployment

For a more flexible deployment, use the Helm chart:

```bash
# Install with Helm
helm install saas-backend ../helm/saas-backend \
  --namespace saas-backend \
  --create-namespace \
  --values custom-values.yaml

# Upgrade
helm upgrade saas-backend ../helm/saas-backend \
  --namespace saas-backend

# Uninstall
helm uninstall saas-backend --namespace saas-backend
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Internet                       │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│           Ingress (with TLS)                    │
│   - api.yourdomain.com → API                    │
│   - flower.yourdomain.com → Flower              │
└───────────────────┬─────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐      ┌────────────────┐
│  API Service  │      │ Flower Service │
│ (ClusterIP)   │      │  (ClusterIP)   │
└───────┬───────┘      └────────┬───────┘
        │                       │
        ▼                       ▼
┌───────────────┐      ┌────────────────┐
│ API Pods (3+) │      │ Flower Pod (1) │
│ - FastAPI     │      │ - Monitoring   │
│ - HPA enabled │      │                │
└───────────────┘      └────────────────┘
        │
        ├─────────────────────┐
        │                     │
        ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│ Celery Workers   │  │  Celery Beat     │
│ (2-5 replicas)   │  │  (1 replica)     │
│ - Background     │  │  - Scheduler     │
│ - HPA enabled    │  │                  │
└──────────────────┘  └──────────────────┘
```

## Components

### API Deployment
- **Replicas**: 3 (default), auto-scales 3-10
- **Resources**: 250m-1000m CPU, 512Mi-1Gi Memory
- **Health Checks**: Liveness and readiness probes
- **Autoscaling**: Based on CPU (70%) and Memory (80%)

### Celery Worker Deployment
- **Replicas**: 2 (default), auto-scales 2-5
- **Resources**: 100m-500m CPU, 256Mi-512Mi Memory
- **Autoscaling**: Based on CPU (75%)

### Celery Beat Deployment
- **Replicas**: 1 (singleton)
- **Resources**: 50m-200m CPU, 128Mi-256Mi Memory

### Flower Deployment
- **Replicas**: 1
- **Resources**: 50m-200m CPU, 128Mi-256Mi Memory
- **Access**: Via ingress at flower.yourdomain.com

## TLS Certificates

TLS certificates are automatically managed by cert-manager using Let's Encrypt.

### Certificate Issuers

- **letsencrypt-staging**: For testing (use first)
- **letsencrypt-prod**: For production

### Testing TLS

```bash
# Check certificate status
kubectl describe certificate saas-backend-tls -n saas-backend

# Check certificate details
kubectl get secret saas-backend-tls -n saas-backend -o yaml
```

## Monitoring

### Logs

```bash
# API logs
kubectl logs -f deployment/saas-backend-api -n saas-backend

# Celery worker logs
kubectl logs -f deployment/saas-backend-celery-worker -n saas-backend

# All logs
kubectl logs -f -l app=saas-backend -n saas-backend
```

### Metrics

```bash
# Pod metrics
kubectl top pods -n saas-backend

# Node metrics
kubectl top nodes
```

### Flower Dashboard

Access Celery monitoring at: `https://flower.yourdomain.com`

## Scaling

### Manual Scaling

```bash
# Scale API
kubectl scale deployment saas-backend-api -n saas-backend --replicas=5

# Scale Celery workers
kubectl scale deployment saas-backend-celery-worker -n saas-backend --replicas=3
```

### Autoscaling

HPA (Horizontal Pod Autoscaler) is configured to automatically scale based on:
- CPU utilization
- Memory utilization

Check HPA status:
```bash
kubectl get hpa -n saas-backend
```

## Database Migration

Run migrations as a Kubernetes Job:

```bash
kubectl run migration-job \
  --image=saas-backend:latest \
  --namespace=saas-backend \
  --restart=Never \
  --command -- alembic upgrade head
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n saas-backend

# Check events
kubectl get events -n saas-backend --sort-by='.lastTimestamp'
```

### Database connection issues

```bash
# Test database connectivity
kubectl run -it --rm debug \
  --image=postgres:16-alpine \
  --namespace=saas-backend \
  --restart=Never \
  -- psql $DATABASE_URL
```

### TLS certificate issues

```bash
# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager

# Check certificate status
kubectl describe certificate -n saas-backend
```

## Security Best Practices

1. **Secrets Management**: Use external secrets management (e.g., HashiCorp Vault, AWS Secrets Manager)
2. **RBAC**: Configure proper Role-Based Access Control
3. **Network Policies**: Restrict pod-to-pod communication
4. **Pod Security**: Enable Pod Security Standards
5. **Image Scanning**: Scan images for vulnerabilities
6. **TLS**: Always use TLS in production
7. **Regular Updates**: Keep Kubernetes and dependencies updated

## Production Checklist

- [ ] Update all secrets in `secret.yaml`
- [ ] Configure proper domain names in `ingress.yaml`
- [ ] Set up external PostgreSQL database
- [ ] Set up external Redis instance
- [ ] Configure backup strategy
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Test autoscaling behavior
- [ ] Verify TLS certificates
- [ ] Set up CI/CD pipeline
- [ ] Configure resource quotas
- [ ] Enable network policies
- [ ] Set up disaster recovery plan

## Cleanup

```bash
# Delete all resources
kubectl delete namespace saas-backend

# Or with Helm
helm uninstall saas-backend --namespace saas-backend
kubectl delete namespace saas-backend
```
