# SaaS Backend Helm Chart

Production-grade Helm chart for deploying the FastAPI SaaS backend framework.

## Features

- FastAPI application deployment with autoscaling
- Celery workers for background tasks
- Celery Beat for scheduled tasks
- Flower for Celery monitoring
- Optional PostgreSQL subchart
- Optional Redis subchart
- Optional MinIO subchart
- TLS certificate management with cert-manager
- Health checks and resource limits
- Horizontal Pod Autoscaler (HPA)

## Prerequisites

- Kubernetes 1.20+
- Helm 3.0+
- cert-manager (for TLS certificates)
- Ingress controller (nginx recommended)

## Installation

### Quick Start (External Database)

Deploy with external PostgreSQL, Redis, and S3:

```bash
helm install saas-backend . \
  --namespace saas-backend \
  --create-namespace \
  --set secrets.databaseUrl="postgresql+asyncpg://user:pass@host:5432/db" \
  --set secrets.redisUrl="redis://host:6379/0" \
  --set secrets.celeryBrokerUrl="redis://host:6379/2" \
  --set secrets.celeryResultBackend="redis://host:6379/3" \
  --set secrets.awsS3Bucket="your-bucket" \
  --set secrets.awsAccessKeyId="your-key" \
  --set secrets.awsSecretAccessKey="your-secret"
```

### Development (With Subcharts)

Deploy with PostgreSQL, Redis, and MinIO included:

```bash
# Update dependencies
helm dependency update

# Install with all subcharts enabled
helm install saas-backend . \
  --namespace saas-backend \
  --create-namespace \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set minio.enabled=true \
  --values dev-values.yaml
```

Create `dev-values.yaml`:

```yaml
# Enable all subcharts for development
postgresql:
  enabled: true

redis:
  enabled: true

minio:
  enabled: true

# Use subchart services
secrets:
  # Use PostgreSQL subchart
  databaseUrl: "postgresql+asyncpg://postgres:postgres@saas-backend-postgresql:5432/saas_db"

  # Use Redis subchart
  redisUrl: "redis://saas-backend-redis-master:6379/0"
  celeryBrokerUrl: "redis://saas-backend-redis-master:6379/2"
  celeryResultBackend: "redis://saas-backend-redis-master:6379/3"

  # Use MinIO subchart
  awsS3Bucket: "saas-uploads"
  awsAccessKeyId: "minioadmin"
  awsSecretAccessKey: "minioadmin"

# Configure MinIO endpoint
config:
  fileStorageProvider: "s3"

# Set MinIO endpoint in API
# Note: Add AWS_ENDPOINT_URL via secrets or configmap
```

## Configuration

### Core Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of API pod replicas | `3` |
| `image.repository` | Container image repository | `saas-backend` |
| `image.tag` | Container image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |

### Autoscaling

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.enabled` | Enable HPA for API | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `3` |
| `autoscaling.maxReplicas` | Maximum replicas | `10` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU % | `70` |
| `autoscaling.targetMemoryUtilizationPercentage` | Target Memory % | `80` |

### Ingress & TLS

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class | `nginx` |
| `ingress.hosts[0].host` | API hostname | `api.yourdomain.com` |
| `ingress.tls[0].secretName` | TLS secret name | `saas-backend-tls` |

### PostgreSQL Subchart

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL subchart | `false` |
| `postgresql.auth.username` | Database username | `postgres` |
| `postgresql.auth.password` | Database password | `postgres` |
| `postgresql.auth.database` | Database name | `saas_db` |
| `postgresql.primary.persistence.size` | Storage size | `8Gi` |

### Redis Subchart

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis subchart | `false` |
| `redis.auth.enabled` | Enable Redis auth | `false` |
| `redis.master.persistence.size` | Storage size | `8Gi` |

### MinIO Subchart

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.enabled` | Enable MinIO subchart | `false` |
| `minio.auth.rootUser` | MinIO root user | `minioadmin` |
| `minio.auth.rootPassword` | MinIO root password | `minioadmin` |
| `minio.defaultBuckets` | Default bucket | `saas-uploads` |
| `minio.persistence.size` | Storage size | `10Gi` |

### Celery Workers

| Parameter | Description | Default |
|-----------|-------------|---------|
| `celeryWorker.enabled` | Enable Celery workers | `true` |
| `celeryWorker.replicaCount` | Number of worker replicas | `2` |
| `celeryWorker.autoscaling.enabled` | Enable HPA for workers | `true` |
| `celeryWorker.autoscaling.maxReplicas` | Maximum worker replicas | `5` |

### Flower Monitoring

| Parameter | Description | Default |
|-----------|-------------|---------|
| `flower.enabled` | Enable Flower | `true` |
| `flower.ingress.enabled` | Enable Flower ingress | `true` |
| `flower.ingress.hosts[0].host` | Flower hostname | `flower.yourdomain.com` |

## Using Subcharts

### Enabling Subcharts

To use the optional subcharts, you need to:

1. **Update dependencies** (download subchart packages):
   ```bash
   helm dependency update
   ```

2. **Enable desired subcharts** in `values.yaml` or via `--set`:
   ```yaml
   postgresql:
     enabled: true

   redis:
     enabled: true

   minio:
     enabled: true
   ```

3. **Configure application to use subcharts**:
   ```yaml
   secrets:
     databaseUrl: "postgresql+asyncpg://postgres:postgres@saas-backend-postgresql:5432/saas_db"
     redisUrl: "redis://saas-backend-redis-master:6379/0"
     awsAccessKeyId: "minioadmin"
     awsSecretAccessKey: "minioadmin"
   ```

### Subchart Service Names

When subcharts are enabled, they create services with predictable names:

- **PostgreSQL**: `<release-name>-postgresql` (e.g., `saas-backend-postgresql`)
- **Redis**: `<release-name>-redis-master` (e.g., `saas-backend-redis-master`)
- **MinIO**: `<release-name>-minio` (e.g., `saas-backend-minio`)

### Production Recommendations

For production deployments:

1. **Use external managed services** (disable subcharts):
   - AWS RDS for PostgreSQL
   - AWS ElastiCache for Redis
   - AWS S3 for file storage
   - Benefits: Better reliability, backups, monitoring

2. **If using subcharts in production**:
   - Enable persistence with adequate storage
   - Configure backups
   - Set resource limits appropriately
   - Use separate nodes/node pools
   - Enable monitoring and alerting

## Examples

### Example 1: Development with All Subcharts

```bash
# Update dependencies first
helm dependency update

# Install
helm install saas-dev . \
  --namespace saas-dev \
  --create-namespace \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set minio.enabled=true \
  --set secrets.secretKey="dev-secret-key-min-32-chars-long" \
  --set secrets.databaseUrl="postgresql+asyncpg://postgres:postgres@saas-dev-postgresql:5432/saas_db" \
  --set secrets.redisUrl="redis://saas-dev-redis-master:6379/0" \
  --set secrets.celeryBrokerUrl="redis://saas-dev-redis-master:6379/2" \
  --set secrets.celeryResultBackend="redis://saas-dev-redis-master:6379/3" \
  --set secrets.awsS3Bucket="saas-uploads" \
  --set secrets.awsAccessKeyId="minioadmin" \
  --set secrets.awsSecretAccessKey="minioadmin" \
  --set config.fileStorageProvider="s3" \
  --set ingress.hosts[0].host="api.dev.local"
```

### Example 2: Production with External Services

```bash
helm install saas-prod . \
  --namespace saas-prod \
  --create-namespace \
  --values production-values.yaml
```

`production-values.yaml`:
```yaml
image:
  tag: "v1.0.0"
  pullPolicy: IfNotPresent

# Use external services (subcharts disabled)
postgresql:
  enabled: false

redis:
  enabled: false

minio:
  enabled: false

secrets:
  secretKey: "<your-secret-key>"
  databaseUrl: "postgresql+asyncpg://user:pass@prod-db.us-east-1.rds.amazonaws.com:5432/saas_db"
  redisUrl: "redis://prod-cache.abc123.0001.use1.cache.amazonaws.com:6379/0"
  celeryBrokerUrl: "redis://prod-cache.abc123.0001.use1.cache.amazonaws.com:6379/2"
  celeryResultBackend: "redis://prod-cache.abc123.0001.use1.cache.amazonaws.com:6379/3"
  awsS3Bucket: "prod-saas-uploads"
  awsAccessKeyId: "<aws-key>"
  awsSecretAccessKey: "<aws-secret>"

config:
  appEnv: "production"
  debug: false
  fileStorageProvider: "s3"

ingress:
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: saas-backend-tls
      hosts:
        - api.yourdomain.com
```

### Example 3: Staging with PostgreSQL Subchart Only

```bash
helm dependency update

helm install saas-staging . \
  --namespace saas-staging \
  --create-namespace \
  --set postgresql.enabled=true \
  --set redis.enabled=false \
  --set minio.enabled=false \
  --set secrets.databaseUrl="postgresql+asyncpg://postgres:postgres@saas-staging-postgresql:5432/saas_db" \
  --set secrets.redisUrl="redis://external-redis:6379/0" \
  --set secrets.awsS3Bucket="staging-bucket"
```

## Upgrading

### Upgrade Release

```bash
helm upgrade saas-backend . \
  --namespace saas-backend \
  --values values.yaml
```

### Update Dependencies

When Chart.yaml dependencies change:

```bash
helm dependency update
helm upgrade saas-backend . --namespace saas-backend
```

## Uninstalling

```bash
# Uninstall release
helm uninstall saas-backend --namespace saas-backend

# Delete namespace (if desired)
kubectl delete namespace saas-backend
```

**Note**: Uninstalling will not delete PersistentVolumeClaims by default. Delete them manually if needed:

```bash
kubectl delete pvc --all --namespace saas-backend
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n saas-backend
kubectl describe pod <pod-name> -n saas-backend
kubectl logs <pod-name> -n saas-backend
```

### Check Subchart Services

```bash
# PostgreSQL
kubectl get svc saas-backend-postgresql -n saas-backend
kubectl run -it --rm debug --image=postgres:16 --restart=Never -- psql -h saas-backend-postgresql -U postgres

# Redis
kubectl get svc saas-backend-redis-master -n saas-backend
kubectl run -it --rm debug --image=redis:7 --restart=Never -- redis-cli -h saas-backend-redis-master ping

# MinIO
kubectl get svc saas-backend-minio -n saas-backend
kubectl port-forward svc/saas-backend-minio 9001:9001
# Access console at http://localhost:9001
```

### Database Migrations

Run database migrations:

```bash
# Connect to API pod
kubectl exec -it deployment/saas-backend-api -n saas-backend -- bash

# Run migrations
alembic upgrade head
```

### Test Connectivity

```bash
# Test API
kubectl port-forward svc/saas-backend-api 8000:8000 -n saas-backend
curl http://localhost:8000/health

# Test Flower
kubectl port-forward svc/saas-backend-flower 5555:5555 -n saas-backend
# Open http://localhost:5555
```

## Advanced Configuration

### Custom Values File

Create a custom values file for your environment:

```bash
# Create custom-values.yaml with your configuration
helm install saas-backend . \
  --namespace saas-backend \
  --create-namespace \
  --values values.yaml \
  --values custom-values.yaml
```

### Secrets Management

For production, use external secrets management:

```yaml
# Use external-secrets operator
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
```

### Resource Optimization

Adjust resources based on load:

```yaml
resources:
  requests:
    cpu: 500m      # Increase for higher load
    memory: 1Gi    # Increase for memory-intensive tasks
  limits:
    cpu: 2000m
    memory: 2Gi

autoscaling:
  minReplicas: 5     # Higher baseline for production
  maxReplicas: 20    # Higher ceiling for traffic spikes
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/yourusername/saas-backend/issues
- Documentation: See project README.md

## License

See project LICENSE file.
