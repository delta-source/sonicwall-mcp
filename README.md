# SonicWall MCP Server

A Model Context Protocol (MCP) server for managing SonicWall firewalls through their REST API. This server allows you to control and configure your SonicWall appliance using AI assistants that support the MCP protocol.

## Features

- **Firewall Rules Management**: List, create, and delete access rules
- **NAT Policy Management**: View and create NAT policies
- **Address Object Management**: Manage address objects and groups
- **Interface Information**: Get network interface details and status
- **System Status**: Monitor appliance health and system information
- **Native Python**: Lightweight native implementation with 1Password CLI integration

## Prerequisites

1. **SonicWall Appliance** with SonicOS API enabled  
2. **Python 3.13+** and **pip** installed
3. **1Password CLI** for secure credential management
4. **Network Access** to your SonicWall management interface

## Quick Start

### 1. Enable SonicOS API on Your SonicWall

First, you need to enable the API on your SonicWall appliance:

**Via Web Interface:**
1. Log in to your SonicWall management interface
2. Navigate to **MANAGE** > **Appliance** > **Base Settings**
3. Scroll to the **SonicOS API** section
4. Check **Enable SonicOS API**
5. Check **Enable RFC-2617 HTTP Basic Access authentication**
6. Click **Accept**

**Via CLI:**
```bash
config
administration
sonicos-api
basic
commit
```

### 2. Clone and Configure

```bash
# Clone or create the project directory
mkdir sonicwall-mcp && cd sonicwall-mcp

# Copy the environment file and configure
cp env.example .env
```

Edit `.env` with your SonicWall details:
```env
SONICWALL_HOST=192.168.1.1
SONICWALL_PORT=443
SONICWALL_USERNAME=admin
SONICWALL_PASSWORD=your_password_here
```

### 3. Set Up Python Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure 1Password CLI

Store your credentials securely in 1Password:
```bash
# Install 1Password CLI if not already installed
brew install 1password-cli

# Create a vault item with your SonicWall credentials
# Item name: sonic_mcp
# Fields: username, password, and configure TOTP for the admin account
```

### 5. Run the Server

```bash
# Run with 1Password CLI integration
./run_with_1password.sh

# Or alternatively, run directly (requires OP_SERVICE_ACCOUNT_TOKEN)
python src/main.py
```

### 6. Test the Connection

The MCP server will connect to your SonicWall using stdio (for Cursor/AI assistants). Check the console output to ensure successful authentication.

## Available Tools

The MCP server provides the following tools for AI assistants:

### Firewall Management
- `list_firewall_rules` - List all access rules (with optional zone filtering)
- `create_firewall_rule` - Create new firewall rules
- `delete_firewall_rule` - Remove existing rules

### NAT Management
- `list_nat_policies` - View NAT policies
- `create_nat_policy` - Create new NAT policies

### Address Objects
- `list_address_objects` - List address objects (with name filtering)
- `create_address_object` - Create host, network, range, or FQDN objects

### System Information
- `get_interface_info` - Get network interface details
- `get_system_status` - View system health and status

## Usage Examples

Once connected to an AI assistant supporting MCP, you can ask questions like:

- "Show me all firewall rules from LAN to WAN"
- "Create a rule to allow HTTP traffic from LAN to DMZ"
- "List all address objects containing 'server'"
- "What's the current system status?"
- "Create an address object for my web server"

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SONICWALL_HOST` | SonicWall IP address | Required |
| `SONICWALL_PORT` | HTTPS port | 443 |
| `SONICWALL_USERNAME` | Admin username | Required |
| `SONICWALL_PASSWORD` | Admin password | Required |
| `MCP_SERVER_PORT` | MCP server port | 8080 |
| `LOG_LEVEL` | Logging level | INFO |

### Environment Configuration

The server loads credentials from 1Password CLI but you can also set environment variables:

```bash
export SONICWALL_HOST="192.168.100.1"
export SONICWALL_PORT="443"
export LOG_LEVEL="DEBUG"
export OP_SERVICE_ACCOUNT_TOKEN="your_1password_token"
```

## Security Considerations

- **Network Security**: Ensure the MCP server can only be accessed by authorized AI assistants
- **Credentials**: Use strong passwords and consider certificate-based authentication
- **Firewall Rules**: The server can modify firewall configurations - use appropriate access controls
- **Logging**: Monitor the logs for any unexpected API calls

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify SonicOS API is enabled
   - Check username/password in `.env`
   - Ensure Basic Auth is enabled

2. **Connection Timeout**
   - Verify network connectivity to SonicWall
   - Check firewall rules allowing HTTPS access
   - Confirm the management port (usually 443)

3. **API Errors**
   - Check SonicWall firmware version (API support varies)
   - Review API documentation for your SonicOS version
   - Enable debug logging for detailed error messages

### Debug Logging

Enable debug logging by setting:
```env
LOG_LEVEL=DEBUG
```

Then restart the MCP server:
```bash
# Stop current process (Ctrl+C) and restart
./run_with_1password.sh
```

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SONICWALL_HOST=192.168.1.1
export SONICWALL_USERNAME=admin
export SONICWALL_PASSWORD=password

# Run the server
python src/main.py
```

### Adding New Tools

1. Implement the tool function in `src/tools.py`
2. Add the tool definition in `src/main.py` (`handle_list_tools`)
3. Add the tool handler in `src/main.py` (`handle_call_tool`)

## API Reference

The server uses the SonicOS REST API. Key endpoints:

- `/api/sonicos/config/access-rule/ipv4` - Firewall rules
- `/api/sonicos/config/nat-policy/ipv4` - NAT policies  
- `/api/sonicos/config/address-object/ipv4` - Address objects
- `/api/sonicos/config/interface/ipv4` - Network interfaces
- `/api/sonicos/status` - System status

## License

This project is provided as-is for educational and automation purposes. Use responsibly and ensure you have proper authorization to manage the target SonicWall appliance.

## Support

For issues related to:
- **SonicOS API**: Consult SonicWall documentation and support
- **MCP Protocol**: Check the Model Context Protocol specification
- **This Server**: Review logs and configuration

---

**⚠️ Warning**: This tool can modify firewall configurations. Test thoroughly in a non-production environment before using on critical infrastructure.
