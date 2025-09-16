"""
SonicWall API Explorer
Dynamic API documentation and endpoint discovery
"""

import json
from typing import Dict, Any, List
try:
    from .sonicwall_client import SonicWallClient
except ImportError:
    from sonicwall_client import SonicWallClient

class SonicWallAPIExplorer:
    """Explore and document SonicWall API endpoints dynamically."""
    
    def __init__(self, client: SonicWallClient):
        self.client = client
        self.discovered_endpoints = {}
        
    async def discover_api_structure(self) -> Dict[str, Any]:
        """Discover the complete API structure by exploring all endpoints."""
        try:
            # Start with the base API endpoints
            base_structure = await self.client._make_request("GET", "")
            
            discovered = {
                "base_url": self.client.base_url,
                "main_categories": {},
                "total_endpoints": 0
            }
            
            # Explore each main category
            for key, url in base_structure.items():
                if key.endswith("_url"):
                    category = key.replace("_url", "")
                    endpoint_path = url.replace(self.client.base_url + "/", "")
                    
                    try:
                        category_data = await self.client._make_request("GET", endpoint_path)
                        discovered["main_categories"][category] = {
                            "url": url,
                            "path": endpoint_path,
                            "endpoints": len(category_data) if isinstance(category_data, dict) else 0,
                            "structure": category_data if isinstance(category_data, dict) else {"data": category_data}
                        }
                        discovered["total_endpoints"] += discovered["main_categories"][category]["endpoints"]
                    except Exception as e:
                        discovered["main_categories"][category] = {
                            "url": url,
                            "path": endpoint_path,
                            "error": str(e),
                            "endpoints": 0
                        }
            
            self.discovered_endpoints = discovered
            return discovered
            
        except Exception as e:
            return {"error": f"Failed to discover API structure: {str(e)}"}
    
    async def get_endpoint_documentation(self, category: str = None, endpoint: str = None) -> Dict[str, Any]:
        """Get documentation for specific endpoints or categories."""
        if not self.discovered_endpoints:
            await self.discover_api_structure()
        
        if category and endpoint:
            # Get specific endpoint details
            try:
                full_path = f"{category}/{endpoint}" if not endpoint.startswith(category) else endpoint
                result = await self.client._make_request("GET", full_path)
                return {
                    "category": category,
                    "endpoint": endpoint,
                    "path": full_path,
                    "data": result
                }
            except Exception as e:
                return {"error": f"Failed to get endpoint {category}/{endpoint}: {str(e)}"}
        
        elif category:
            # Get category details
            if category in self.discovered_endpoints.get("main_categories", {}):
                return self.discovered_endpoints["main_categories"][category]
            else:
                return {"error": f"Category '{category}' not found"}
        
        else:
            # Return overview
            return self.discovered_endpoints
    
    async def search_endpoints(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for endpoints containing specific terms."""
        if not self.discovered_endpoints:
            await self.discover_api_structure()
        
        results = []
        search_lower = search_term.lower()
        
        for category, data in self.discovered_endpoints.get("main_categories", {}).items():
            if search_lower in category.lower():
                results.append({
                    "type": "category",
                    "name": category,
                    "match_type": "category_name",
                    "url": data.get("url", ""),
                    "path": data.get("path", "")
                })
            
            # Search within category structure
            if isinstance(data.get("structure"), dict):
                for key, value in data["structure"].items():
                    if search_lower in key.lower():
                        results.append({
                            "type": "endpoint",
                            "category": category,
                            "name": key,
                            "match_type": "endpoint_name",
                            "url": value if isinstance(value, str) else "",
                            "path": data.get("path", "") + "/" + key.replace("_url", "")
                        })
        
        return results
    
    async def get_api_summary(self) -> Dict[str, Any]:
        """Get a summary of all available API capabilities."""
        if not self.discovered_endpoints:
            await self.discover_api_structure()
        
        summary = {
            "device_info": {
                "base_url": self.discovered_endpoints.get("base_url", ""),
                "total_categories": len(self.discovered_endpoints.get("main_categories", {})),
                "total_endpoints": self.discovered_endpoints.get("total_endpoints", 0)
            },
            "categories": []
        }
        
        for category, data in self.discovered_endpoints.get("main_categories", {}).items():
            category_summary = {
                "name": category,
                "endpoint_count": data.get("endpoints", 0),
                "path": data.get("path", ""),
                "available": "error" not in data,
                "description": self._get_category_description(category)
            }
            summary["categories"].append(category_summary)
        
        return summary
    
    def _get_category_description(self, category: str) -> str:
        """Get human-readable description for API categories."""
        descriptions = {
            "device": "Device information and management",
            "network": "Network configuration and interfaces",
            "objects": "Address objects, service objects, and groups", 
            "policies": "Firewall rules, NAT policies, and routing",
            "actions": "Administrative actions and operations",
            "reportings": "Logging, monitoring, and reporting",
            "license": "License management and information",
            "administration": "Global administration settings",
            "time": "Time and NTP configuration",
            "certificates": "Certificate management",
            "snmp": "SNMP configuration and monitoring",
            "firmware": "Firmware management and updates",
            "user": "User authentication and management",
            "log": "Logging configuration and view",
            "switch_controller": "Switch controller functionality",
            "sonicpoint": "Wireless access point management"
        }
        return descriptions.get(category, f"API category: {category}")

async def explore_api_endpoints(client: SonicWallClient, search_term: str = None, category: str = None) -> str:
    """MCP tool function to explore SonicWall API endpoints."""
    explorer = SonicWallAPIExplorer(client)
    
    if search_term:
        results = await explorer.search_endpoints(search_term)
        if results:
            response = f"🔍 Found {len(results)} API endpoints matching '{search_term}':\n\n"
            for result in results:
                response += f"• **{result['name']}** ({result['type']})\n"
                response += f"  Category: {result.get('category', 'N/A')}\n"
                response += f"  Path: {result['path']}\n\n"
        else:
            response = f"❌ No API endpoints found matching '{search_term}'"
        return response
    
    elif category:
        docs = await explorer.get_endpoint_documentation(category)
        if "error" in docs:
            return f"❌ {docs['error']}"
        
        response = f"📋 **{category.upper()}** API Category:\n\n"
        response += f"Path: {docs.get('path', 'N/A')}\n"
        response += f"Endpoints: {docs.get('endpoints', 0)}\n\n"
        
        if "structure" in docs and isinstance(docs["structure"], dict):
            response += "Available endpoints:\n"
            for key, value in docs["structure"].items():
                endpoint_name = key.replace("_url", "")
                response += f"• {endpoint_name}\n"
                if isinstance(value, str) and value.startswith("/api"):
                    response += f"  → {value}\n"
        
        return response
    
    else:
        summary = await explorer.get_api_summary()
        response = f"🌐 **SonicWall API Overview**\n\n"
        response += f"Base URL: {summary['device_info']['base_url']}\n"
        response += f"Categories: {summary['device_info']['total_categories']}\n"
        response += f"Total Endpoints: {summary['device_info']['total_endpoints']}\n\n"
        response += "**Available Categories:**\n"
        
        for cat in summary['categories']:
            status = "✅" if cat['available'] else "❌"
            response += f"{status} **{cat['name']}** ({cat['endpoint_count']} endpoints)\n"
            response += f"   {cat['description']}\n"
            response += f"   Path: {cat['path']}\n\n"
        
        response += "\n💡 Use search_term parameter to find specific endpoints"
        response += "\n💡 Use category parameter to explore a specific category"
        
        return response
