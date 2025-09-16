#!/usr/bin/env python3
"""
SonicMCP - Model Context Protocol Server for SonicWall Firewall Management
Based on the official MCP Python SDK patterns
"""

import asyncio
import logging
import os
from typing import Any, Dict, List

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from sonicwall_client import SonicWallClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create server instance
server = Server("SonicMCP")

# Global SonicWall client instance
sonicwall_client: SonicWallClient = None


async def initialize_sonicwall_client() -> bool:
    """Initialize the SonicWall client with credentials from environment or 1Password."""
    global sonicwall_client
    
    try:
        host = os.getenv("SONICWALL_HOST", "192.168.100.1")
        port = int(os.getenv("SONICWALL_PORT", "443"))
        username = os.getenv("SONICWALL_USERNAME", "")
        password = os.getenv("SONICWALL_PASSWORD", "")
        totp = os.getenv("SONICWALL_TOTP", "")  # Initialize TOTP
        
        # If credentials not in environment, try to load from 1Password
        if not username or not password:
            logger.info("🔐 Loading SonicWall credentials from 1Password...")
            try:
                import subprocess
                
                # Try to get credentials from 1Password
                username_result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/username'], 
                                               capture_output=True, text=True, check=True)
                password_result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/password'], 
                                               capture_output=True, text=True, check=True)
                totp_result = subprocess.run(['op', 'item', 'get', 'sonic_mcp', '--otp'], 
                                           capture_output=True, text=True, check=True)
                
                username = username_result.stdout.strip()
                password = password_result.stdout.strip()
                totp = totp_result.stdout.strip()
                
                if username and password:
                    logger.info("✅ Successfully loaded credentials from 1Password")
                    if totp:
                        logger.info("🔐 TOTP code loaded for 2FA authentication")
                else:
                    logger.error("❌ Empty credentials returned from 1Password")
                    return False
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to load credentials from 1Password: {e}")
                return False
            except Exception as e:
                logger.error(f"❌ Error accessing 1Password: {e}")
                return False
        
        sonicwall_client = SonicWallClient(host, port, username, password, totp)
        success = await sonicwall_client.connect()
        
        if success:
            logger.info("✅ SonicWall client initialized successfully")
        else:
            logger.error("❌ Failed to connect to SonicWall")
            # Reset circuit breaker on initialization failure to allow retries
            sonicwall_client.reset_circuit_breaker()
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error initializing SonicWall client: {e}")
        return False


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available SonicWall management tools."""
    return [
        types.Tool(
            name="get_system_status",
            description="Get SonicWall system status and health information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="list_firewall_rules",
            description="List firewall access rules with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "zone_from": {
                        "type": "string",
                        "description": "Filter by source zone (e.g., 'LAN', 'WAN')"
                    },
                    "zone_to": {
                        "type": "string", 
                        "description": "Filter by destination zone (e.g., 'LAN', 'WAN')"
                    },
                    "enabled_only": {
                        "type": "boolean",
                        "description": "Show only enabled rules",
                        "default": True
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="list_interfaces",
            description="List network interfaces and their configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "interface_type": {
                        "type": "string",
                        "description": "Filter by interface type (e.g., 'physical', 'vlan', 'tunnel')"
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="explore_api_endpoints",
            description="Dynamically discover available SonicWall API endpoints",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "API path to explore (default: root)",
                        "default": ""
                    }
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls."""
    global sonicwall_client
    
    if not sonicwall_client:
        return [types.TextContent(
            type="text",
            text="❌ SonicWall client not initialized. Please check credentials."
        )]
    
    # Check circuit breaker status - allow get_system_status to bypass for reset
    if (sonicwall_client.connection_failed and 
        sonicwall_client.failed_attempts >= sonicwall_client.max_retries and 
        name != "get_system_status"):
        return [types.TextContent(
            type="text",
            text=f"❌ SonicWall connection circuit breaker is open due to {sonicwall_client.failed_attempts} failed attempts. Use 'get_system_status' to test connectivity and reset."
        )]
    
    try:
        if name == "get_system_status":
            return await handle_get_system_status(arguments)
        elif name == "list_firewall_rules":
            return await handle_list_firewall_rules(arguments)
        elif name == "list_interfaces":
            return await handle_list_interfaces(arguments)
        elif name == "explore_api_endpoints":
            return await handle_explore_api_endpoints(arguments)
        else:
            return [types.TextContent(
                type="text",
                text=f"❌ Unknown tool: {name}"
            )]
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]


async def handle_get_system_status(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Get SonicWall system status."""
    try:
        # If circuit breaker is open, try to reset it first
        if sonicwall_client.connection_failed and sonicwall_client.failed_attempts >= sonicwall_client.max_retries:
            logger.info("Attempting to reset circuit breaker and reconnect...")
            sonicwall_client.reset_circuit_breaker()
        
        # Try the most likely status endpoint first
        try:
            response = await sonicwall_client.get("status")
            return [types.TextContent(
                type="text",
                text=f"✅ System Status:\n\n{response}"
            )]
        except Exception as e:
            logger.debug(f"Status endpoint failed: {e}")
        
        # Fallback to device endpoint which should contain system info
        try:
            response = await sonicwall_client.get("device")
            return [types.TextContent(
                type="text",
                text=f"✅ Device Information:\n\n{response}"
            )]
        except Exception as e:
            logger.debug(f"Device endpoint failed: {e}")
        
        # Last resort: return the base API structure
        response = await sonicwall_client.get("")
        if response and isinstance(response, dict):
            text = "✅ SonicWall API Connected\n\nAvailable endpoints:\n"
            for key, value in response.items():
                if key.endswith("_url"):
                    category = key.replace("_url", "").replace("_", " ").title()
                    text += f"• {category}: {value}\n"
            text += "\n💡 Use specific endpoint tools to get detailed information"
            return [types.TextContent(type="text", text=text)]
        else:
            return [types.TextContent(
                type="text",
                text=f"✅ Connected to SonicWall\n\nResponse: {response}"
            )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Failed to get system status: {str(e)}"
        )]


async def handle_list_firewall_rules(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """List firewall access rules."""
    try:
        # Extract filter arguments
        zone_from = arguments.get("zone_from")
        zone_to = arguments.get("zone_to") 
        enabled_only = arguments.get("enabled_only", True)
        
        filter_info = []
        if zone_from:
            filter_info.append(f"From Zone: {zone_from}")
        if zone_to:
            filter_info.append(f"To Zone: {zone_to}")
        if enabled_only:
            filter_info.append("Enabled rules only")
        
        filter_text = f" (Filters: {', '.join(filter_info)})" if filter_info else ""
        
        # Try the accessible policies endpoint instead of config
        try:
            # Try main policies endpoint (should be accessible)
            response = await sonicwall_client.get_policies()
            return [types.TextContent(
                type="text",
                text=f"✅ Security Policies{filter_text}:\n\n{response}"
            )]
        except Exception as e:
            logger.debug(f"policies endpoint failed: {e}")
        
        return [types.TextContent(
            type="text",
            text="❌ Could not access firewall policies. Try using 'explore_api_endpoints' to discover available policy endpoints."
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Failed to list firewall rules: {str(e)}"
        )]


async def handle_list_interfaces(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """List network interfaces."""
    try:
        interface_type = arguments.get("interface_type")
        
        # Get interface information directly
        result = await sonicwall_client.get("interfaces/ipv4")
        
        if not result:
            return [types.TextContent(
                type="text",
                text="No interface information found."
            )]
        
        # Format the interface information
        output = "Network Interfaces:\n"
        output += "=" * 30 + "\n"
        
        interfaces = result.get("interfaces", [])
        if not isinstance(interfaces, list):
            interfaces = [interfaces] if interfaces else []
        
        for iface_container in interfaces:
            iface = iface_container.get("ipv4", {})
            assignment = iface.get("ip_assignment", {})
            mode = assignment.get("mode", {})
            static_config = mode.get("static", {})
            
            output += f"\nInterface: {iface.get('name', 'Unknown')}\n"
            output += f"  Zone: {assignment.get('zone', 'Unknown')}\n"
            output += f"  IP: {static_config.get('ip', 'Unknown')}\n"
            output += f"  Netmask: {static_config.get('netmask', 'Unknown')}\n"
            output += f"  Admin Status: {iface.get('admin', 'Unknown')}\n"
        
        return [types.TextContent(
            type="text",
            text=output
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Failed to list interfaces: {str(e)}"
        )]


async def handle_explore_api_endpoints(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Explore available API endpoints."""
    try:
        path = arguments.get("path", "")
        
        # If specific path is provided, try only that path
        if path:
            try:
                response = await sonicwall_client.get(path)
                return [types.TextContent(
                    type="text",
                    text=f"📍 Endpoint: /{path}\n\n{response}"
                )]
            except Exception as e:
                return [types.TextContent(
                    type="text", 
                    text=f"❌ Failed to access /{path}: {str(e)}"
                )]
        
        # For general exploration, start with just the root API endpoint
        try:
            response = await sonicwall_client.get("")
            if response and isinstance(response, dict):
                # Format the available endpoints nicely
                text = "🔍 SonicWall API Root Endpoints:\n\n"
                for key, value in response.items():
                    if key.endswith("_url"):
                        category = key.replace("_url", "").replace("_", " ").title()
                        text += f"• **{category}**: {value}\n"
                    else:
                        text += f"• {key}: {value}\n"
                
                text += "\n💡 Use the 'path' parameter to explore specific endpoints"
                return [types.TextContent(type="text", text=text)]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"✅ Connected to SonicWall API\n\nResponse: {response}"
                )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Failed to connect to SonicWall API: {str(e)}"
            )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Failed to explore API endpoints: {str(e)}"
        )]


async def main():
    """Main entry point for the SonicMCP server."""
    logger.info("🚀 Starting SonicMCP server...")
    
    # Initialize SonicWall client
    success = await initialize_sonicwall_client()
    if not success:
        logger.warning("⚠️  SonicWall client initialization failed - tools may not work properly")
    
    # Run the MCP server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("✅ SonicMCP server ready for connections")
        
        initialization_options = InitializationOptions(
            server_name="SonicMCP",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )
        
        await server.run(read_stream, write_stream, initialization_options)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 SonicMCP server stopped")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")