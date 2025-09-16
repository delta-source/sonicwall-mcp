#!/usr/bin/env python3
"""
Debug script to test the complete SonicWall TFA authentication flow
"""

import asyncio
import httpx
import subprocess
import logging
import json
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TFADebugger:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.totp: Optional[str] = None
        self.bearer_token: Optional[str] = None
        
    async def load_credentials(self):
        """Load credentials from 1Password"""
        logger.info("🔑 Loading credentials from 1Password...")
        
        try:
            # Get username
            result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/username'],
                                  capture_output=True, text=True, check=True)
            self.username = result.stdout.strip()
            logger.info(f"✅ Username: {self.username}")
            
            # Get password
            result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/password'],
                                  capture_output=True, text=True, check=True)
            self.password = result.stdout.strip()
            logger.info(f"✅ Password: [REDACTED - {len(self.password)} chars]")
            
            # Get TOTP
            result = subprocess.run(['op', 'item', 'get', 'sonic_mcp', '--otp'],
                                  capture_output=True, text=True, check=True)
            self.totp = result.stdout.strip()
            logger.info(f"✅ TOTP: {self.totp}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to load credentials: {e}")
            return False
    
    async def test_basic_auth(self):
        """Test basic digest authentication"""
        logger.info("\n" + "="*50)
        logger.info("🔐 TESTING BASIC DIGEST AUTH")
        logger.info("="*50)
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                url = f"{self.base_url}/api/sonicos"
                auth = httpx.DigestAuth(self.username, self.password)
                
                response = await client.get(url, auth=auth)
                
                logger.info(f"📡 Request: GET {url}")
                logger.info(f"🔒 Auth: Digest ({self.username})")
                logger.info(f"📈 Response: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("✅ Basic digest auth SUCCESS")
                    return True
                else:
                    logger.error(f"❌ Basic digest auth FAILED: {response.status_code}")
                    logger.error(f"❌ Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Basic auth exception: {str(e)}")
            return False
    
    async def test_tfa_auth(self):
        """Test TFA authentication"""
        logger.info("\n" + "="*50)
        logger.info("🔐 TESTING TFA AUTHENTICATION")
        logger.info("="*50)
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                url = f"{self.base_url}/api/sonicos/tfa"
                auth = httpx.DigestAuth(self.username, self.password)
                
                tfa_data = {
                    "user": self.username,
                    "password": self.password,
                    "tfa": self.totp
                }
                
                headers = {"Content-Type": "application/json"}
                
                logger.info(f"📡 Request: POST {url}")
                logger.info(f"🔒 Auth: Digest ({self.username})")
                logger.info(f"📦 Data: {json.dumps({**tfa_data, 'password': '[REDACTED]'}, indent=2)}")
                
                response = await client.post(url, auth=auth, json=tfa_data, headers=headers)
                
                logger.info(f"📈 Response: {response.status_code}")
                logger.info(f"📋 Headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        logger.info(f"📄 Response JSON:")
                        logger.info(json.dumps(result, indent=2))
                        
                        # Try to extract bearer token
                        if result.get("status", {}).get("success", False):
                            bearer_token = result.get("status", {}).get("info", [{}])[0].get("bearer_token")
                            if bearer_token:
                                self.bearer_token = bearer_token
                                logger.info(f"✅ TFA SUCCESS - Bearer token obtained: {bearer_token[:20]}...")
                                return True
                            else:
                                logger.warning("⚠️ TFA response missing bearer token")
                                return False
                        else:
                            logger.error("❌ TFA returned success=false")
                            return False
                    except json.JSONDecodeError:
                        logger.error(f"❌ Invalid JSON response: {response.text}")
                        return False
                else:
                    logger.error(f"❌ TFA authentication FAILED: {response.status_code}")
                    try:
                        error_json = response.json()
                        logger.error(f"❌ Error details:")
                        logger.error(json.dumps(error_json, indent=2))
                    except:
                        logger.error(f"❌ Response text: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ TFA auth exception: {str(e)}")
            return False
    
    async def test_management_session(self):
        """Test starting management session"""
        if not self.bearer_token:
            logger.warning("⚠️ No bearer token available for management session test")
            return False
            
        logger.info("\n" + "="*50)
        logger.info("🔧 TESTING MANAGEMENT SESSION")
        logger.info("="*50)
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                url = f"{self.base_url}/api/sonicos/start-management"
                headers = {"Authorization": f"Bearer {self.bearer_token}"}
                
                logger.info(f"📡 Request: POST {url}")
                logger.info(f"🔒 Auth: Bearer {self.bearer_token[:20]}...")
                
                response = await client.post(url, headers=headers)
                
                logger.info(f"📈 Response: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        logger.info(f"📄 Response JSON:")
                        logger.info(json.dumps(result, indent=2))
                        logger.info("✅ Management session SUCCESS")
                        return True
                    except json.JSONDecodeError:
                        logger.info(f"✅ Management session SUCCESS (no JSON response)")
                        return True
                elif response.status_code == 400:
                    try:
                        result = response.json()
                        message = result.get("status", {}).get("info", [{}])[0].get("message", "")
                        if "Already in management" in message:
                            logger.info("✅ Management session already active")
                            return True
                        else:
                            logger.warning(f"⚠️ Management session error: {message}")
                            return False
                    except:
                        logger.error(f"❌ Management session failed: {response.text}")
                        return False
                else:
                    logger.error(f"❌ Management session FAILED: {response.status_code}")
                    try:
                        error_json = response.json()
                        logger.error(f"❌ Error details:")
                        logger.error(json.dumps(error_json, indent=2))
                    except:
                        logger.error(f"❌ Response text: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Management session exception: {str(e)}")
            return False
    
    async def test_config_endpoint(self):
        """Test accessing configuration endpoint"""
        if not self.bearer_token:
            logger.warning("⚠️ No bearer token available for config endpoint test")
            return False
            
        logger.info("\n" + "="*50)
        logger.info("🔍 TESTING CONFIGURATION ENDPOINT ACCESS")
        logger.info("="*50)
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                url = f"{self.base_url}/api/sonicos/interfaces/ipv4"
                headers = {"Authorization": f"Bearer {self.bearer_token}"}
                
                logger.info(f"📡 Request: GET {url}")
                logger.info(f"🔒 Auth: Bearer {self.bearer_token[:20]}...")
                
                response = await client.get(url, headers=headers)
                
                logger.info(f"📈 Response: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        logger.info("✅ Configuration endpoint ACCESS SUCCESS")
                        logger.info(f"📄 Response preview: {str(result)[:200]}...")
                        return True
                    except json.JSONDecodeError:
                        logger.info("✅ Configuration endpoint SUCCESS (no JSON)")
                        return True
                else:
                    logger.error(f"❌ Configuration endpoint FAILED: {response.status_code}")
                    try:
                        error_json = response.json()
                        logger.error(f"❌ Error details:")
                        logger.error(json.dumps(error_json, indent=2))
                    except:
                        logger.error(f"❌ Response text: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Config endpoint exception: {str(e)}")
            return False
    
    async def run_full_test(self):
        """Run complete authentication flow test"""
        logger.info("🚀 STARTING COMPLETE TFA AUTHENTICATION DEBUG")
        logger.info("="*70)
        
        # Step 1: Load credentials
        if not await self.load_credentials():
            logger.error("💥 FAILED - Could not load credentials")
            return False
        
        # Step 2: Test basic auth
        if not await self.test_basic_auth():
            logger.error("💥 FAILED - Basic digest authentication failed")
            return False
        
        # Step 3: Test TFA
        if not await self.test_tfa_auth():
            logger.error("💥 FAILED - TFA authentication failed")
            return False
        
        # Step 4: Test management session
        if not await self.test_management_session():
            logger.error("💥 FAILED - Management session failed")
            return False
        
        # Step 5: Test config endpoint
        if not await self.test_config_endpoint():
            logger.error("💥 FAILED - Configuration endpoint access failed")
            return False
        
        logger.info("\n" + "="*70)
        logger.info("🎉 SUCCESS - Complete authentication flow working!")
        logger.info("="*70)
        return True

async def main():
    # Replace with your SonicWall's IP
    base_url = "https://10.1.1.1"
    
    debugger = TFADebugger(base_url)
    success = await debugger.run_full_test()
    
    if not success:
        logger.error("\n💥 Authentication flow has issues that need to be resolved")
        exit(1)
    else:
        logger.info("\n🎉 Authentication flow is working correctly!")
        exit(0)

if __name__ == "__main__":
    asyncio.run(main())

