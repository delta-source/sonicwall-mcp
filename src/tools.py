"""
SonicWall MCP Tools
Implementation of various SonicWall management tools
"""

import json
import logging
from typing import Dict, Any, Optional, List
from sonicwall_client import SonicWallClient

logger = logging.getLogger(__name__)

async def list_firewall_rules(client: SonicWallClient, zone_from: Optional[str] = None, zone_to: Optional[str] = None) -> str:
    """List firewall access rules, optionally filtered by zones."""
    try:
        # Get access rules
        result = await client.get_config("access-rule/ipv4")
        
        if not result:
            return "No firewall rules found."
        
        # Parse and format the rules
        rules = []
        access_rules = result.get("access-rule", {}).get("ipv4", [])
        
        if not isinstance(access_rules, list):
            access_rules = [access_rules] if access_rules else []
        
        for rule in access_rules:
            rule_info = {
                "name": rule.get("name", "Unnamed"),
                "from": rule.get("from", "Any"),
                "to": rule.get("to", "Any"), 
                "source": rule.get("source", {}).get("any", "Any"),
                "destination": rule.get("destination", {}).get("any", "Any"),
                "service": rule.get("service", {}).get("any", "Any"),
                "action": rule.get("action", "Unknown"),
                "enabled": rule.get("enable", False)
            }
            
            # Apply zone filters if specified
            if zone_from and rule_info["from"] != zone_from:
                continue
            if zone_to and rule_info["to"] != zone_to:
                continue
                
            rules.append(rule_info)
        
        if not rules:
            return "No firewall rules match the specified criteria."
        
        # Format output
        output = "Firewall Rules:\n"
        output += "=" * 50 + "\n"
        
        for i, rule in enumerate(rules, 1):
            output += f"\n{i}. {rule['name']}\n"
            output += f"   From: {rule['from']} → To: {rule['to']}\n"
            output += f"   Source: {rule['source']}\n"
            output += f"   Destination: {rule['destination']}\n"
            output += f"   Service: {rule['service']}\n"
            output += f"   Action: {rule['action']}\n"
            output += f"   Enabled: {rule['enabled']}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to list firewall rules: {str(e)}")
        return f"Error listing firewall rules: {str(e)}"

async def create_firewall_rule(client: SonicWallClient, name: str, from_zone: str, to_zone: str, 
                             source: str, destination: str, service: str, action: str) -> str:
    """Create a new firewall access rule."""
    try:
        rule_data = {
            "access-rule": {
                "ipv4": {
                    "name": name,
                    "from": from_zone,
                    "to": to_zone,
                    "source": {"any": True} if source.lower() == "any" else {"address": source},
                    "destination": {"any": True} if destination.lower() == "any" else {"address": destination},
                    "service": {"any": True} if service.lower() == "any" else {"service": service},
                    "action": action,
                    "enable": True
                }
            }
        }
        
        # Create the rule
        result = await client.post_config("access-rule/ipv4", rule_data)
        
        # Commit the changes
        await client.commit_config()
        
        return f"Successfully created firewall rule '{name}'"
        
    except Exception as e:
        logger.error(f"Failed to create firewall rule: {str(e)}")
        return f"Error creating firewall rule: {str(e)}"

async def delete_firewall_rule(client: SonicWallClient, rule_id: str) -> str:
    """Delete a firewall access rule by ID or name."""
    try:
        # Try to delete by name first
        result = await client.delete_config(f"access-rule/ipv4/name/{rule_id}")
        
        # Commit the changes
        await client.commit_config()
        
        return f"Successfully deleted firewall rule '{rule_id}'"
        
    except Exception as e:
        logger.error(f"Failed to delete firewall rule: {str(e)}")
        return f"Error deleting firewall rule: {str(e)}"

async def get_interface_info(client: SonicWallClient, interface_name: Optional[str] = None) -> str:
    """Get network interface information."""
    try:
        if interface_name:
            result = await client.get(f"interfaces/ipv4/{interface_name}")
        else:
            result = await client.get("interfaces/ipv4")
        
        if not result:
            return "No interface information found."
        
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
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to get interface info: {str(e)}")
        return f"Error getting interface information: {str(e)}"

async def get_system_status(client: SonicWallClient) -> str:
    """Get SonicWall system status and health information."""
    try:
        # Get system status
        result = await client.get_status()
        
        if not result:
            return "No system status information available."
        
        # Format system information
        output = "SonicWall System Status:\n"
        output += "=" * 25 + "\n"
        
        # Extract useful status information
        if "system" in result:
            system = result["system"]
            output += f"Model: {system.get('model', 'Unknown')}\n"
            output += f"Serial: {system.get('serial', 'Unknown')}\n"
            output += f"Firmware: {system.get('firmware-version', 'Unknown')}\n"
            output += f"Uptime: {system.get('up-time', 'Unknown')}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to get system status: {str(e)}")
        return f"Error getting system status: {str(e)}"

async def list_nat_policies(client: SonicWallClient) -> str:
    """List NAT policies."""
    try:
        result = await client.get_config("nat-policy/ipv4")
        
        if not result:
            return "No NAT policies found."
        
        # Format NAT policies
        output = "NAT Policies:\n"
        output += "=" * 15 + "\n"
        
        policies = result.get("nat-policy", {}).get("ipv4", [])
        if not isinstance(policies, list):
            policies = [policies] if policies else []
        
        for i, policy in enumerate(policies, 1):
            output += f"\n{i}. {policy.get('name', 'Unnamed')}\n"
            output += f"   Original Source: {policy.get('original-source', 'Any')}\n"
            output += f"   Translated Source: {policy.get('translated-source', 'Any')}\n"
            output += f"   Original Destination: {policy.get('original-destination', 'Any')}\n"
            output += f"   Translated Destination: {policy.get('translated-destination', 'Any')}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to list NAT policies: {str(e)}")
        return f"Error listing NAT policies: {str(e)}"

async def create_nat_policy(client: SonicWallClient, name: str, 
                          original_source: Optional[str] = None,
                          translated_source: Optional[str] = None,
                          original_destination: Optional[str] = None,
                          translated_destination: Optional[str] = None) -> str:
    """Create a new NAT policy."""
    try:
        policy_data = {
            "nat-policy": {
                "ipv4": {
                    "name": name,
                    "original-source": original_source or "any",
                    "translated-source": translated_source or "any",
                    "original-destination": original_destination or "any",
                    "translated-destination": translated_destination or "any"
                }
            }
        }
        
        result = await client.post_config("nat-policy/ipv4", policy_data)
        await client.commit_config()
        
        return f"Successfully created NAT policy '{name}'"
        
    except Exception as e:
        logger.error(f"Failed to create NAT policy: {str(e)}")
        return f"Error creating NAT policy: {str(e)}"

async def list_address_objects(client: SonicWallClient, name_filter: Optional[str] = None) -> str:
    """List address objects."""
    try:
        result = await client.get_config("address-object/ipv4")
        
        if not result:
            return "No address objects found."
        
        # Format address objects
        output = "Address Objects:\n"
        output += "=" * 20 + "\n"
        
        objects = result.get("address-object", {}).get("ipv4", [])
        if not isinstance(objects, list):
            objects = [objects] if objects else []
        
        for i, obj in enumerate(objects, 1):
            name = obj.get('name', 'Unnamed')
            
            # Apply name filter if specified
            if name_filter and name_filter.lower() not in name.lower():
                continue
            
            output += f"\n{i}. {name}\n"
            output += f"   Type: {obj.get('type', 'Unknown')}\n"
            output += f"   Zone: {obj.get('zone', 'Unknown')}\n"
            
            if 'host' in obj:
                output += f"   Host: {obj['host'].get('ip', 'Unknown')}\n"
            elif 'network' in obj:
                output += f"   Network: {obj['network'].get('subnet', 'Unknown')}\n"
            elif 'range' in obj:
                output += f"   Range: {obj['range'].get('begin', 'Unknown')} - {obj['range'].get('end', 'Unknown')}\n"
            elif 'fqdn' in obj:
                output += f"   FQDN: {obj['fqdn'].get('domain', 'Unknown')}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to list address objects: {str(e)}")
        return f"Error listing address objects: {str(e)}"

async def create_address_object(client: SonicWallClient, name: str, obj_type: str, value: str, zone: str) -> str:
    """Create a new address object."""
    try:
        # Build the address object data based on type
        obj_data = {
            "address-object": {
                "ipv4": {
                    "name": name,
                    "zone": zone
                }
            }
        }
        
        if obj_type == "host":
            obj_data["address-object"]["ipv4"]["host"] = {"ip": value}
        elif obj_type == "network":
            obj_data["address-object"]["ipv4"]["network"] = {"subnet": value}
        elif obj_type == "range":
            # Expect value in format "start_ip-end_ip"
            if "-" in value:
                start, end = value.split("-", 1)
                obj_data["address-object"]["ipv4"]["range"] = {"begin": start.strip(), "end": end.strip()}
            else:
                return "Error: Range format should be 'start_ip-end_ip'"
        elif obj_type == "fqdn":
            obj_data["address-object"]["ipv4"]["fqdn"] = {"domain": value}
        else:
            return f"Error: Unsupported address object type '{obj_type}'"
        
        result = await client.post_config("address-object/ipv4", obj_data)
        await client.commit_config()
        
        return f"Successfully created address object '{name}'"
        
    except Exception as e:
        logger.error(f"Failed to create address object: {str(e)}")
        return f"Error creating address object: {str(e)}"
