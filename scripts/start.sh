#!/bin/bash
# Complete startup script for SaaS Backend
# Handles service startup, migrations, and verification

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${1}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ ${1}${NC}"
}

print_error() {
    echo -e "${RED}❌ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  ${1}${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  ${1}${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running!"
        echo "Please start Docker and try again."
        exit 1
    fi
}

# Check if .env exists
check_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from .env.example..."
        cp .env.example .env
        print_success "Created .env file"
        print_warning "Please review .env and update SECRET_KEY before production use!"
    fi
}

# Main script
main() {
    print_header "🚀 SaaS Backend Framework - Startup"

    # Checks
    print_header "📋 Pre-flight Checks"
    check_docker
    print_success "Docker is running"

    check_env
    print_success "Environment configured"

    # Start infrastructure services
    print_header "🏗️  Starting Infrastructure Services"
    print_info "Starting PostgreSQL, Redis, MinIO..."

    docker-compose up -d postgres redis minio minio_client

    print_info "Waiting for services to be healthy (30 seconds)..."
    sleep 30

    print_success "Infrastructure services started"

    # Check service health
    print_header "🏥 Health Checks"

    # PostgreSQL
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        print_success "PostgreSQL is healthy"
    else
        print_error "PostgreSQL is not responding"
        exit 1
    fi

    # Redis
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        print_success "Redis is healthy"
    else
        print_error "Redis is not responding"
        exit 1
    fi

    # Initialize Database
    print_header "🗄️  Database Initialization"

    # Check if migrations exist
    MIGRATIONS_COUNT=$(ls -1 alembic/versions/*.py 2>/dev/null | wc -l || echo "0")

    if [ "$MIGRATIONS_COUNT" -eq "0" ]; then
        print_info "No migrations found. Generating initial migration..."

        # Start API temporarily to generate migration
        docker-compose up -d api
        sleep 10

        docker-compose exec -T api alembic revision --autogenerate -m "Initial migration with all models"

        print_success "Migration generated in alembic/versions/"
        print_info "Stopping API to apply migrations..."
        docker-compose stop api
        sleep 2
    else
        print_info "Found $MIGRATIONS_COUNT existing migration(s)"
    fi

    # Apply migrations
    print_info "Applying database migrations..."
    docker-compose up -d api
    sleep 10

    docker-compose exec -T api alembic upgrade head
    print_success "Migrations applied successfully"

    # Start all services
    print_header "🎬 Starting All Services"
    docker-compose up -d

    print_info "Waiting for services to stabilize (20 seconds)..."
    sleep 20

    # Verify deployment
    print_header "✅ Verification"

    # Check API
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "API is responding"
    else
        print_warning "API might not be ready yet (try: curl http://localhost:8000/health)"
    fi

    # Check database tables
    print_info "Database tables:"
    docker-compose exec -T postgres psql -U postgres saas_db -c "\dt" 2>/dev/null | grep "public" || print_warning "Could not list tables"

    # Final status
    print_header "🎉 Startup Complete!"

    echo ""
    print_success "All services are running!"
    echo ""
    echo "📍 Service URLs:"
    echo "   • API:          http://localhost:8000"
    echo "   • API Docs:     http://localhost:8000/docs"
    echo "   • Health:       http://localhost:8000/health"
    echo "   • Metrics:      http://localhost:8000/metrics"
    echo "   • Adminer:      http://localhost:8080"
    echo "   • MinIO Console: http://localhost:9001"
    echo "   • Flower:       http://localhost:5555"
    echo ""
    echo "🧪 Next Steps:"
    echo "   1. Run tests:        ./run_tests.sh"
    echo "   2. Try CLI:          python cli.py auth register"
    echo "   3. View logs:        docker-compose logs -f api"
    echo "   4. Check health:     python cli.py health check-all"
    echo ""
    print_info "View running services: docker-compose ps"
    echo ""
}

# Handle script interruption
trap 'echo -e "\n${RED}Startup interrupted${NC}"; exit 1' INT TERM

# Run main
main
