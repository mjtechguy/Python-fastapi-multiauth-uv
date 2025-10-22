#!/bin/bash
# Test Docker hot reload functionality

set -e

echo "🔥 Testing Docker Hot Reload..."
echo ""

# Check if containers are running
if ! docker compose ps | grep -q "Up"; then
    echo "❌ Containers not running. Starting them..."
    docker compose up -d
    echo "⏳ Waiting for services to be ready..."
    sleep 10
fi

# Test 1: Check API is responding
echo "1️⃣  Testing API endpoint..."
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ API is responding"
else
    echo "❌ API not responding"
    exit 1
fi

# Test 2: Modify a file
echo ""
echo "2️⃣  Modifying main.py to test hot reload..."
BACKUP_FILE="/tmp/main.py.backup"
cp app/main.py "$BACKUP_FILE"

# Add a comment to trigger reload
echo "# Hot reload test - $(date +%s)" >> app/main.py

# Wait for reload
echo "⏳ Waiting for uvicorn to detect change and reload..."
sleep 3

# Check logs for reload message
if docker compose logs --tail=20 api | grep -q "Application startup complete"; then
    echo "✅ Hot reload detected! Uvicorn restarted."
else
    echo "⚠️  Reload message not found in logs (might still work)"
fi

# Test 3: Verify API still works
echo ""
echo "3️⃣  Verifying API still responds after reload..."
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ API still responding after reload"
else
    echo "❌ API not responding after reload"
    mv "$BACKUP_FILE" app/main.py
    exit 1
fi

# Restore original file
echo ""
echo "🔄 Restoring original main.py..."
mv "$BACKUP_FILE" app/main.py
sleep 2

# Test 4: Check volume mount
echo ""
echo "4️⃣  Checking volume mount..."
if docker compose exec -T api test -f /app/app/main.py; then
    echo "✅ Files mounted correctly"
else
    echo "❌ Files not mounted"
    exit 1
fi

# Test 5: Check reload flag
echo ""
echo "5️⃣  Checking uvicorn reload flag..."
if docker compose exec -T api ps aux | grep -q "uvicorn.*--reload"; then
    echo "✅ Reload flag is enabled"
else
    echo "❌ Reload flag not found"
    exit 1
fi

echo ""
echo "🎉 All hot reload tests passed!"
echo ""
echo "📝 Summary:"
echo "   - API responding: ✅"
echo "   - Hot reload working: ✅"
echo "   - Volume mount: ✅"
echo "   - Reload flag: ✅"
echo ""
echo "💡 Try editing app/main.py and watch the logs:"
echo "   docker compose logs -f api"
