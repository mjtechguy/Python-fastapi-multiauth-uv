#!/bin/bash
# Database initialization script
# Run this after starting services for the first time

set -e

echo "🗄️  Initializing database..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check if migrations exist
MIGRATIONS_COUNT=$(ls -1 alembic/versions/*.py 2>/dev/null | wc -l)

if [ "$MIGRATIONS_COUNT" -eq 0 ]; then
    echo "📝 No migrations found. Generating initial migration..."

    # Generate migration
    docker-compose exec -T api alembic revision --autogenerate -m "Initial migration with all models"

    echo "✅ Migration generated"
else
    echo "📋 Found $MIGRATIONS_COUNT existing migration(s)"
fi

# Apply migrations
echo "🔄 Applying migrations..."
docker-compose exec -T api alembic upgrade head

echo "✅ Database initialized successfully!"

# Show tables
echo ""
echo "📊 Database tables:"
docker-compose exec -T postgres psql -U postgres saas_db -c "\dt" | grep public || echo "No tables found (this might be an error)"

echo ""
echo "🎉 Database is ready!"
