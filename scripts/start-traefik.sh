#!/bin/bash

# SaaS Backend Framework - Traefik Production Startup Script
# This script starts the entire application stack with Traefik for production deployments
# with automatic SSL/TLS certificates and DNS-based routing.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓ ${NC}$1"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${NC}$1"
}

print_error() {
    echo -e "${RED}✗ ${NC}$1"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Check if Docker is running
check_docker() {
    print_header "Checking Prerequisites"

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi

    print_success "Docker is running"

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi

    print_success "Docker Compose is installed"
}

# Check Traefik configuration
check_traefik_config() {
    print_header "Checking Traefik Configuration"

    # Check if Traefik configuration exists
    if [ ! -f "traefik/traefik.yml" ]; then
        print_error "Traefik configuration not found at traefik/traefik.yml"
        exit 1
    fi
    print_success "Traefik configuration found"

    # Check if .env file exists for Traefik
    if [ ! -f "traefik/.env" ]; then
        print_warning ".env file not found in traefik/ directory"

        if [ -f "traefik/.env.example" ]; then
            print_info "Copying traefik/.env.example to traefik/.env"
            cp traefik/.env.example traefik/.env
            print_warning "IMPORTANT: Edit traefik/.env and update DOMAIN and ACME_EMAIL before proceeding!"
            print_info "Press Enter to continue after updating the configuration, or Ctrl+C to exit"
            read -r
        else
            print_error "traefik/.env.example not found"
            exit 1
        fi
    else
        print_success "Traefik .env file found"
    fi

    # Source the Traefik .env to check configuration
    if [ -f "traefik/.env" ]; then
        # shellcheck disable=SC1091
        source traefik/.env

        if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "example.com" ]; then
            print_error "DOMAIN not configured in traefik/.env"
            print_info "Please update DOMAIN in traefik/.env to your actual domain"
            exit 1
        fi
        print_success "Domain configured: $DOMAIN"

        if [ -z "$ACME_EMAIL" ] || [ "$ACME_EMAIL" = "your-email@example.com" ]; then
            print_warning "ACME_EMAIL not configured or using default"
            print_info "It's recommended to set a valid email for Let's Encrypt notifications"
        else
            print_success "ACME email configured: $ACME_EMAIL"
        fi
    fi

    # Check if email in traefik.yml needs updating
    if grep -q "your-email@example.com" traefik/traefik.yml; then
        print_warning "Default email found in traefik/traefik.yml"
        print_info "Please update the email address in traefik/traefik.yml for Let's Encrypt"
    fi
}

# Check/Create main .env file
check_env_file() {
    print_header "Checking Environment Configuration"

    if [ ! -f ".env" ]; then
        print_warning ".env file not found"

        if [ -f ".env.example" ]; then
            print_info "Copying .env.example to .env"
            cp .env.example .env
            print_success "Created .env file with default values"
            print_warning "Review .env and update SECRET_KEY and other production settings!"
        else
            print_error ".env.example not found"
            exit 1
        fi
    else
        print_success ".env file exists"
    fi
}

# Start services
start_services() {
    print_header "Starting Services with Traefik"

    print_info "Starting infrastructure services (PostgreSQL, Redis, MinIO)..."
    docker-compose -f docker-compose.yml -f docker-compose.traefik.yml up -d postgres redis minio

    print_info "Waiting for infrastructure to be healthy (30 seconds)..."
    sleep 30

    print_info "Starting application services (API, Celery, Flower) with Traefik..."
    docker-compose -f docker-compose.yml -f docker-compose.traefik.yml up -d

    print_success "All services started"
}

# Check if migrations exist
check_migrations() {
    print_header "Checking Database Migrations"

    MIGRATIONS_COUNT=$(find alembic/versions -name "*.py" -type f 2>/dev/null | wc -l)

    if [ "$MIGRATIONS_COUNT" -eq "0" ]; then
        print_warning "No migrations found in alembic/versions/"
        print_info "Generating initial migration..."

        # Wait for database to be ready
        print_info "Waiting for database to be ready..."
        sleep 10

        docker-compose -f docker-compose.yml -f docker-compose.traefik.yml exec -T api alembic revision --autogenerate -m "Initial migration with all models"

        if [ $? -eq 0 ]; then
            print_success "Migration generated successfully"
        else
            print_error "Failed to generate migration"
            exit 1
        fi
    else
        print_success "Found $MIGRATIONS_COUNT migration(s)"
    fi
}

# Apply migrations
apply_migrations() {
    print_header "Applying Database Migrations"

    print_info "Running: alembic upgrade head"
    docker-compose -f docker-compose.yml -f docker-compose.traefik.yml exec -T api alembic upgrade head

    if [ $? -eq 0 ]; then
        print_success "Migrations applied successfully"
    else
        print_error "Failed to apply migrations"
        exit 1
    fi
}

# Verify services
verify_services() {
    print_header "Verifying Services"

    # Wait for API to be ready
    print_info "Waiting for API to be ready..."
    sleep 10

    # Check if services are running
    SERVICES=("traefik" "postgres" "redis" "minio" "api" "celery_worker" "celery_beat" "flower")

    for service in "${SERVICES[@]}"; do
        if docker-compose -f docker-compose.yml -f docker-compose.traefik.yml ps | grep -q "saas_$service.*Up"; then
            print_success "$service is running"
        else
            print_warning "$service might not be running correctly"
        fi
    done

    # Test API health endpoint (local connection)
    print_info "Testing API health endpoint..."
    if docker-compose -f docker-compose.yml -f docker-compose.traefik.yml exec -T api curl -f http://localhost:8000/health/ping &> /dev/null; then
        print_success "API health check passed"
    else
        print_warning "API health check failed (this is normal if API is still starting)"
    fi
}

# Print next steps
print_next_steps() {
    print_header "Setup Complete! 🎉"

    # Get domain from Traefik .env
    DOMAIN="yourdomain.com"
    if [ -f "traefik/.env" ]; then
        # shellcheck disable=SC1091
        source traefik/.env
    fi

    echo ""
    echo -e "${GREEN}Your SaaS backend is now running with Traefik!${NC}"
    echo ""
    echo -e "${BLUE}📝 Next Steps:${NC}"
    echo ""
    echo "1. Configure DNS records for your domain:"
    echo "   - api.$DOMAIN     → Your server IP"
    echo "   - traefik.$DOMAIN → Your server IP"
    echo "   - db.$DOMAIN      → Your server IP (optional)"
    echo "   - minio.$DOMAIN   → Your server IP (optional)"
    echo "   - s3.$DOMAIN      → Your server IP (optional)"
    echo "   - flower.$DOMAIN  → Your server IP (optional)"
    echo ""
    echo "2. Wait for DNS propagation (can take up to 48 hours, usually minutes)"
    echo ""
    echo "3. Access your services via HTTPS:"
    echo -e "   ${BLUE}API:${NC}              https://api.$DOMAIN"
    echo -e "   ${BLUE}API Docs:${NC}         https://api.$DOMAIN/docs"
    echo -e "   ${BLUE}Traefik Dashboard:${NC} https://traefik.$DOMAIN (admin/changeme)"
    echo -e "   ${BLUE}Database UI:${NC}      https://db.$DOMAIN (requires auth)"
    echo -e "   ${BLUE}MinIO Console:${NC}    https://minio.$DOMAIN"
    echo -e "   ${BLUE}S3 API:${NC}           https://s3.$DOMAIN"
    echo -e "   ${BLUE}Flower:${NC}           https://flower.$DOMAIN (requires auth)"
    echo ""
    echo -e "${YELLOW}⚠️  Important:${NC}"
    echo "   - SSL certificates will be generated automatically by Let's Encrypt"
    echo "   - First certificate generation may take a few minutes"
    echo "   - Change default passwords (Traefik dashboard: admin/changeme)"
    echo "   - Update SECRET_KEY in .env for production"
    echo ""
    echo -e "${BLUE}📊 Useful Commands:${NC}"
    echo ""
    echo "   # View logs"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f"
    echo ""
    echo "   # View Traefik logs"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.traefik.yml logs -f traefik"
    echo ""
    echo "   # Restart a service"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.traefik.yml restart api"
    echo ""
    echo "   # Stop all services"
    echo "   docker-compose -f docker-compose.yml -f docker-compose.traefik.yml down"
    echo ""
    echo "   # Check certificate"
    echo "   docker exec saas_traefik cat /certificates/acme.json"
    echo ""
    echo -e "${GREEN}Documentation:${NC}"
    echo "   - Traefik Setup: traefik/README.md"
    echo "   - API Testing: docs/TESTING.md"
    echo "   - CLI Tool: docs/CLI_REFERENCE.md"
    echo "   - Deployment: docs/DEPLOYMENT_CHECKLIST.md"
    echo ""
}

# Main execution
main() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                  ║${NC}"
    echo -e "${GREEN}║         SaaS Backend Framework - Traefik Startup Script          ║${NC}"
    echo -e "${GREEN}║                                                                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_docker
    check_traefik_config
    check_env_file
    start_services
    check_migrations
    apply_migrations
    verify_services
    print_next_steps
}

# Run main function
main
