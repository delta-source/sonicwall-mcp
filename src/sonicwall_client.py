"""
SonicWall API Client
Handles authentication and API communication with SonicWall devices
"""

import httpx
import json
import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urljoin
from httpx._auth import DigestAuth

logger = logging.getLogger(__name__)

class SonicWallClient:
    """SonicWall API client for managing firewall configurations."""
    
    def __init__(self, host: str, port: int = 443, username: str = "", password: str = "", totp: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.totp = totp
        self.base_url = f"https://{host}:{port}/api/sonicos"
        self.bearer_token = None
        self.client = None
        self.auth = DigestAuth(username, password)
        self.connection_failed = False
        self.failed_attempts = 0
        self.max_retries = 3
        
    async def connect(self) -> bool:
        """Connect and test authentication with the SonicWall device."""
        self.client = httpx.AsyncClient(
            verify=False, 
            timeout=30.0,
            headers={
                "User-Agent": "SonicMCP/1.0",
                "Accept": "application/json"
            }
        )
        
        try:
            # Test basic authentication by making a simple API call
            test_url = urljoin(self.base_url, "")  # Base API endpoint
            
            response = await self.client.get(
                test_url,
                auth=self.auth
            )
            
            if response.status_code == 200:
                logger.info("✅ Basic authentication successful with SonicWall")
                
                # Try TFA authentication directly to get bearer token
                if self.totp:
                    try:
                        logger.info("🔐 Attempting TFA authentication for bearer token...")
                        tfa_url = f"{self.base_url}/tfa"
                        tfa_data = {
                            "user": self.username,
                            "password": self.password,
                            "tfa": self.totp
                        }
                        
                        tfa_response = await self.client.post(
                            tfa_url,
                            auth=self.auth,
                            json=tfa_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if tfa_response.status_code == 200:
                            tfa_result = tfa_response.json()
                            if tfa_result.get("status", {}).get("success", False):
                                logger.info("✅ TFA authentication successful!")
                                # Extract bearer token from TFA response
                                bearer_token = tfa_result.get("status", {}).get("info", [{}])[0].get("bearer_token")
                                if bearer_token:
                                    self.bearer_token = bearer_token
                                    logger.info("✅ Bearer token obtained for API access")
                                    
                                    # Start management session for configuration access
                                    try:
                                        logger.info("🔧 Starting management session...")
                                        mgmt_url = f"{self.base_url}/start-management"
                                        mgmt_response = await self.client.post(
                                            mgmt_url,
                                            headers={"Authorization": f"Bearer {self.bearer_token}"}
                                        )
                                        
                                        if mgmt_response.status_code == 200:
                                            logger.info("✅ Management session started successfully!")
                                            mgmt_result = mgmt_response.json()
                                            logger.info(f"🔧 Management response: {mgmt_result}")
                                        elif mgmt_response.status_code == 400:
                                            # Check if it's "Already in management" which is actually success
                                            try:
                                                mgmt_result = mgmt_response.json()
                                                message = mgmt_result.get("status", {}).get("info", [{}])[0].get("message", "")
                                                if "Already in management" in message:
                                                    logger.info("✅ Management session already active!")
                                                else:
                                                    logger.warning(f"⚠️ Management session failed: {mgmt_response.status_code}")
                                                    logger.warning(f"⚠️ Management error response: {mgmt_response.text}")
                                            except:
                                                logger.warning(f"⚠️ Management session failed: {mgmt_response.status_code}")
                                                logger.warning(f"⚠️ Management error response: {mgmt_response.text}")
                                        else:
                                            logger.warning(f"⚠️ Management session failed: {mgmt_response.status_code}")
                                            logger.warning(f"⚠️ Management error response: {mgmt_response.text}")
                                    except Exception as mgmt_error:
                                        logger.warning(f"⚠️ Management session failed: {str(mgmt_error)}")
                                else:
                                    logger.warning("⚠️ No bearer token found in TFA response")
                            else:
                                logger.warning("⚠️ TFA authentication returned success=false")
                        else:
                            logger.warning(f"⚠️ TFA authentication failed: {tfa_response.status_code}")
                            
                    except Exception as tfa_error:
                        logger.warning(f"⚠️ TFA authentication failed: {str(tfa_error)}")
                else:
                    logger.warning("⚠️ No TOTP code available - bearer token authentication not possible")
                
                # Reset circuit breaker on successful connection
                self.connection_failed = False
                self.failed_attempts = 0
                return True
            else:
                logger.error(f"❌ Authentication failed: {response.status_code} - {response.text}")
                self.connection_failed = True
                self.failed_attempts += 1
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            self.connection_failed = True
            self.failed_attempts += 1
            return False
    
    async def disconnect(self):
        """Disconnect from the SonicWall device."""
        if self.client:
            try:
                await self.client.aclose()
                logger.info("Disconnected from SonicWall")
            except Exception as e:
                logger.warning(f"Disconnect failed: {str(e)}")
            finally:
                self.client = None
                self.session_token = None
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated API request with circuit breaker protection."""
        if not self.client:
            raise Exception("Client not connected. Call connect() first.")
        
        # Circuit breaker: if we've failed too many times, don't try again
        if self.connection_failed and self.failed_attempts >= self.max_retries:
            raise Exception(f"Circuit breaker open: too many failed requests ({self.failed_attempts})")
        
        # Construct URL properly - ensure endpoint doesn't start with /
        clean_endpoint = endpoint.lstrip('/')
        if clean_endpoint:
            url = f"{self.base_url}/{clean_endpoint}"
        else:
            url = self.base_url
            
        headers = {}
        
        # Use bearer token authentication if available, otherwise fall back to digest auth
        auth = None
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
            logger.debug("🔐 Using bearer token authentication")
        else:
            auth = self.auth
            logger.debug("🔐 Using digest authentication")
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers, auth=auth)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=headers, json=data, auth=auth)
            elif method.upper() == "PUT":
                response = await self.client.put(url, headers=headers, json=data, auth=auth)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=headers, auth=auth)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Reset failure count on successful request
            self.failed_attempts = 0
            self.connection_failed = False
            
            # Handle different content types
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    # SonicWall sometimes returns malformed JSON, try to fix it
                    text = response.text
                    # Fix common SonicWall JSON issues
                    # Remove trailing commas before closing braces/brackets
                    import re
                    text = re.sub(r',(\s*[}\]])', r'\1', text)
                    # Fix missing commas between object properties
                    text = re.sub(r'"\s*\n\s*"', r'",\n    "', text)
                    
                    try:
                        import json as json_module
                        return json_module.loads(text)
                    except json_module.JSONDecodeError:
                        # If still can't parse, return as text with error info
                        return {
                            "error": "Invalid JSON from SonicWall", 
                            "json_error": str(e),
                            "raw_response": text[:500] + "..." if len(text) > 500 else text
                        }
            else:
                return {"text": response.text, "status_code": response.status_code}
                
        except httpx.HTTPStatusError as e:
            self.failed_attempts += 1
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text} (attempt {self.failed_attempts})")
            
            # Mark connection as failed for auth errors
            if e.response.status_code in (401, 403):
                self.connection_failed = True
                
            raise Exception(f"API request failed: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self.failed_attempts += 1
            logger.error(f"Request failed: {str(e)} (attempt {self.failed_attempts})")
            self.connection_failed = True
            raise
    
    async def get_config(self, path: str = "") -> Dict[str, Any]:
        """Get configuration from the specified path."""
        endpoint = f"config/{path}" if path else "config"
        return await self._make_request("GET", endpoint)
    
    async def post_config(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Post configuration to the specified path."""
        endpoint = f"config/{path}"
        return await self._make_request("POST", endpoint, data)
    
    async def put_config(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Put configuration to the specified path."""
        endpoint = f"config/{path}"
        return await self._make_request("PUT", endpoint, data)
    
    async def delete_config(self, path: str) -> Dict[str, Any]:
        """Delete configuration at the specified path."""
        endpoint = f"config/{path}"
        return await self._make_request("DELETE", endpoint)
    
    async def commit_config(self) -> Dict[str, Any]:
        """Commit pending configuration changes."""
        return await self._make_request("POST", "config/pending")
    
    async def get_status(self, path: str = "") -> Dict[str, Any]:
        """Get status information from the specified path."""
        endpoint = f"status/{path}" if path else "status"
        return await self._make_request("GET", endpoint)
    
    async def get_reporting(self, path: str = "") -> Dict[str, Any]:
        """Get reporting information from the specified path."""
        # Use the absolute URL structure for reportings
        if not path:
            # Replace the /device part with /reportings in the base URL
            url = self.base_url.replace('/api/sonicos', '/api/sonicos/reportings')
        else:
            url = self.base_url.replace('/api/sonicos', f'/api/sonicos/reportings/{path}')
        
        # Make request with full URL instead of endpoint
        headers = {}
        if self.session_token:
            headers["X-Session-Id"] = self.session_token
        
        # Use session cookies if available
        cookies = self.session_cookies if self.session_cookies else None
        response = await self.client.get(url, headers=headers, auth=self.auth, cookies=cookies)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                # SonicWall sometimes returns malformed JSON, try to fix it
                text = response.text
                # Fix common SonicWall JSON issues
                import re
                text = re.sub(r',(\s*[}\]])', r'\1', text)
                text = re.sub(r'"\s*\n\s*"', r'",\n    "', text)
                
                try:
                    import json as json_module
                    return json_module.loads(text)
                except json_module.JSONDecodeError:
                    return {
                        "error": "Invalid JSON from SonicWall", 
                        "json_error": str(e),
                        "raw_response": text[:500] + "..." if len(text) > 500 else text
                    }
        else:
            return {"text": response.text, "status_code": response.status_code}
    
    async def get_network(self) -> Dict[str, Any]:
        """Get network information from main network endpoint."""
        url = self.base_url.replace('/api/sonicos', '/api/sonicos/network')
        headers = {}
        if self.session_token:
            headers["X-Session-Id"] = self.session_token
        
        # Use session cookies if available
        cookies = self.session_cookies if self.session_cookies else None
        response = await self.client.get(url, headers=headers, auth=self.auth, cookies=cookies)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                # SonicWall sometimes returns malformed JSON, try to fix it
                text = response.text
                # Fix common SonicWall JSON issues
                import re
                text = re.sub(r',(\s*[}\]])', r'\1', text)
                text = re.sub(r'"\s*\n\s*"', r'",\n    "', text)
                
                try:
                    import json as json_module
                    return json_module.loads(text)
                except json_module.JSONDecodeError:
                    return {
                        "error": "Invalid JSON from SonicWall", 
                        "json_error": str(e),
                        "raw_response": text[:500] + "..." if len(text) > 500 else text
                    }
        else:
            return {"text": response.text, "status_code": response.status_code}
    
    async def get_policies(self) -> Dict[str, Any]:
        """Get policies information from main policies endpoint."""
        url = self.base_url.replace('/api/sonicos', '/api/sonicos/policies')
        headers = {}
        if self.session_token:
            headers["X-Session-Id"] = self.session_token
        
        # Use session cookies if available
        cookies = self.session_cookies if self.session_cookies else None
        response = await self.client.get(url, headers=headers, auth=self.auth, cookies=cookies)
        response.raise_for_status()
        
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                # SonicWall sometimes returns malformed JSON, try to fix it
                text = response.text
                # Fix common SonicWall JSON issues
                import re
                text = re.sub(r',(\s*[}\]])', r'\1', text)
                text = re.sub(r'"\s*\n\s*"', r'",\n    "', text)
                
                try:
                    import json as json_module
                    return json_module.loads(text)
                except json_module.JSONDecodeError:
                    return {
                        "error": "Invalid JSON from SonicWall", 
                        "json_error": str(e),
                        "raw_response": text[:500] + "..." if len(text) > 500 else text
                    }
        else:
            return {"text": response.text, "status_code": response.status_code}
    
    async def get(self, endpoint: str = "") -> Dict[str, Any]:
        """Make a generic GET request to any endpoint."""
        return await self._make_request("GET", endpoint)
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker to allow new connection attempts."""
        self.connection_failed = False
        self.failed_attempts = 0
        logger.info("Circuit breaker reset - allowing new connection attempts")
