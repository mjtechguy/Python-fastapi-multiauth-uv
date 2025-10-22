#!/bin/bash
# Complete test runner script for SaaS Backend Framework

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Check if services are up
check_services() {
    if ! docker-compose ps | grep -q "Up"; then
        print_info "Services not running. Starting services..."
        docker-compose up -d
        print_info "Waiting for services to be ready (30s)..."
        sleep 30
    fi
    print_success "Services are running"
}

# Main script
main() {
    print_header "SaaS Backend Test Suite Runner"

    # Parse arguments
    TEST_TYPE="${1:-all}"

    # Check Docker
    print_header "Checking Prerequisites"
    check_docker

    # Check/Start services
    check_services

    # Run migrations
    print_header "Running Database Migrations"
    docker-compose exec -T api alembic upgrade head || {
        print_error "Migration failed"
        exit 1
    }
    print_success "Migrations completed"

    # Install dependencies
    print_header "Installing Test Dependencies"
    uv pip install -e ".[dev,cli]" > /dev/null 2>&1 || {
        print_error "Failed to install dependencies"
        exit 1
    }
    print_success "Dependencies installed"

    # Run tests based on type
    case $TEST_TYPE in
        "e2e"|"all")
            print_header "Running E2E Tests"
            pytest tests/e2e/ -v --tb=short || {
                print_error "E2E tests failed"
                exit 1
            }
            print_success "E2E tests passed"
            ;;
    esac

    # Coverage report
    if [ "$TEST_TYPE" = "coverage" ]; then
        print_header "Generating Coverage Report"
        pytest tests/e2e/ --cov=app --cov-report=html --cov-report=term
        print_success "Coverage report generated: htmlcov/index.html"
    fi

    # CLI test
    if [ "$TEST_TYPE" = "cli" ] || [ "$TEST_TYPE" = "all" ]; then
        print_header "Testing CLI Tool"
        python cli.py --help > /dev/null || {
            print_error "CLI tool test failed"
            exit 1
        }
        print_success "CLI tool is working"
    fi

    # Health check
    print_header "Running Health Checks"
    python cli.py health check-all || {
        print_error "Health checks failed"
        exit 1
    }
    print_success "All services healthy"

    print_header "Test Suite Complete!"
    print_success "All tests passed ✓"
    echo ""
    print_info "Next steps:"
    echo "  - View coverage: open htmlcov/index.html"
    echo "  - Try CLI: python cli.py --help"
    echo "  - API docs: http://localhost:8000/docs"
    echo ""
}

# Run main with arguments
main "$@"
