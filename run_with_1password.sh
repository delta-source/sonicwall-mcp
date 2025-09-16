#!/bin/bash

# SonicWall MCP Server with 1Password CLI integration
# This script injects secrets from 1Password at runtime

set -e

echo "🔐 Starting SonicWall MCP Server with 1Password CLI integration..."

# Check if 1Password CLI is available
if ! command -v op &> /dev/null; then
    echo "❌ 1Password CLI is not installed or not in PATH"
    exit 1
fi

# Check if service account token is available  
if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
    echo "❌ OP_SERVICE_ACCOUNT_TOKEN not set"
    echo "   Service account token required for Docker container"
    exit 1
fi

echo "✅ 1Password service account ready"

# Export environment variables with 1Password secret injection
export SONICWALL_HOST="192.168.100.1"
export SONICWALL_PORT="443"
export SONICWALL_USERNAME=$(op read "op://sonic_mcp/sonic_mcp/username")
export SONICWALL_PASSWORD=$(op read "op://sonic_mcp/sonic_mcp/password")
export MCP_SERVER_PORT="8080"
export LOG_LEVEL="INFO"

echo "✅ Secrets loaded from 1Password"
echo "🚀 Starting MCP server..."

# Run the MCP server
python src/main.py
