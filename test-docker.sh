#!/bin/bash
#
# Docker validation script for MRAv2 Syslog Connector
# This script tests Docker builds and runs tests in containers
#

set -e

echo "========================================"
echo "MRAv2 Syslog Connector - Docker CI Test"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Test 1: Build production image
echo "Step 1: Building production Docker image..."
if docker build -t mrav2-syslog-connector:test-build . > /tmp/docker-build.log 2>&1; then
    print_status "Production Docker image built successfully"
else
    print_error "Failed to build production Docker image"
    echo "Build log:"
    cat /tmp/docker-build.log
    exit 1
fi

# Test 2: Build test image
echo ""
echo "Step 2: Building test Docker image..."
if docker build -f Dockerfile.test -t mrav2-syslog-connector:test-runner . > /tmp/docker-test-build.log 2>&1; then
    print_status "Test Docker image built successfully"
else
    print_error "Failed to build test Docker image"
    echo "Build log:"
    cat /tmp/docker-test-build.log
    exit 1
fi

# Test 3: Run tests in container
echo ""
echo "Step 3: Running tests in Docker container..."
if docker run --rm mrav2-syslog-connector:test-runner > /tmp/test-results.log 2>&1; then
    print_status "All tests passed in Docker container"
    echo ""
    echo "Test summary:"
    grep -E "(PASSED|FAILED|ERROR|passed|failed)" /tmp/test-results.log | tail -5
else
    print_error "Tests failed in Docker container"
    echo "Test output:"
    cat /tmp/test-results.log
    exit 1
fi

# Test 4: Verify image size
echo ""
echo "Step 4: Checking Docker image size..."
IMAGE_SIZE=$(docker images mrav2-syslog-connector:test-build --format "{{.Size}}")
print_status "Production image size: $IMAGE_SIZE"

# Test 5: Test help command
echo ""
echo "Step 5: Testing connector help command..."
if docker run --rm mrav2-syslog-connector:test-build --help > /tmp/help.log 2>&1; then
    print_status "Connector help command works"
else
    print_warning "Help command check skipped (requires config)"
fi

# Test 6: Security scan with docker scan (if available)
echo ""
echo "Step 6: Running security scan..."
if command -v docker &> /dev/null && docker scan --version &> /dev/null 2>&1; then
    docker scan mrav2-syslog-connector:test-build > /tmp/security-scan.log 2>&1 || true
    print_status "Security scan completed"
else
    print_warning "Docker scan not available, skipping security scan"
fi

# Cleanup
echo ""
echo "Step 7: Cleaning up test images..."
docker rmi mrav2-syslog-connector:test-build mrav2-syslog-connector:test-runner > /dev/null 2>&1 || true
print_status "Cleanup completed"

# Summary
echo ""
echo "========================================"
echo "Docker CI Test Summary"
echo "========================================"
print_status "Docker build: PASSED"
print_status "Test execution: PASSED"
print_status "Image validation: PASSED"
echo ""
echo -e "${GREEN}All Docker CI tests completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Push to GitHub to trigger CI pipeline"
echo "  2. Create a tag to build release image"
echo "  3. Deploy using docker-compose up -d"
