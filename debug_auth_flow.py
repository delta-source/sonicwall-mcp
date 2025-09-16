#!/usr/bin/env python3
"""
Debug SonicWall Authentication Flow
Test each step of authentication and see exactly what's happening
"""

import asyncio
import httpx
import json
import subprocess
from urllib.parse import urljoin

async def debug_auth_flow():
    # Get credentials from 1Password
    print("=== Getting Credentials from 1Password ===")
    
    try:
        username_result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/username'], 
                                       capture_output=True, text=True, check=True)
        username = username_result.stdout.strip()
        print(f"✅ Username: {username}")
        
        password_result = subprocess.run(['op', 'read', 'op://sonic_mcp/sonic_mcp/password'], 
                                       capture_output=True, text=True, check=True)
        password = password_result.stdout.strip()
        print(f"✅ Password: {len(password)} characters")
        
        totp_result = subprocess.run(['op', 'item', 'get', 'sonic_mcp', '--otp'], 
                                   capture_output=True, text=True, check=True)
        totp = totp_result.stdout.strip()
        print(f"✅ TOTP: {totp}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get credentials: {e}")
        return

    # Base configuration
    base_url = "https://sonicwall.internal.visco.graphics/api/sonicos"
    print(f"\n=== Base URL: {base_url} ===")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        # Step 1: Test basic connectivity
        print("\n=== Step 1: Basic Connectivity Test ===")
        try:
            auth = httpx.DigestAuth(username, password)
            response = await client.get(base_url, auth=auth)
            print(f"GET {base_url}")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
        except Exception as e:
            print(f"❌ Basic connectivity failed: {e}")
            return

        # Step 2: TFA Authentication
        print("\n=== Step 2: TFA Authentication ===")
        tfa_url = f"{base_url}/tfa"
        tfa_data = {
            "user": username,
            "password": password,
            "tfa": totp
        }
        
        try:
            print(f"POST {tfa_url}")
            sanitized_data = {
                "user": username,
                "password": f"[{len(password)} chars]",
                "tfa": totp
            }
            print(f"Data: {json.dumps(sanitized_data, indent=2)}")
            
            tfa_response = await client.post(
                tfa_url,
                json=tfa_data,
                auth=httpx.DigestAuth(username, password),
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Status: {tfa_response.status_code}")
            print(f"Headers: {dict(tfa_response.headers)}")
            print(f"Response: {tfa_response.text}")
            
            if tfa_response.status_code == 200:
                tfa_result = tfa_response.json()
                print(f"Parsed TFA Result: {json.dumps(tfa_result, indent=2)}")
                
                # Extract bearer token
                bearer_token = tfa_result.get("status", {}).get("info", [{}])[0].get("bearer_token")
                if bearer_token:
                    print(f"✅ Bearer token extracted: {bearer_token[:20]}...")
                else:
                    print("❌ No bearer token found in response")
                    return
            else:
                print(f"❌ TFA failed with status {tfa_response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ TFA request failed: {e}")
            return

        # Step 3: Start Management Session
        print("\n=== Step 3: Start Management Session ===")
        mgmt_url = f"{base_url}/start-management"
        
        try:
            print(f"POST {mgmt_url}")
            print(f"Authorization: Bearer {bearer_token[:20]}...")
            
            mgmt_response = await client.post(
                mgmt_url,
                headers={"Authorization": f"Bearer {bearer_token}"}
            )
            
            print(f"Status: {mgmt_response.status_code}")
            print(f"Headers: {dict(mgmt_response.headers)}")
            print(f"Response: {mgmt_response.text}")
            
            if mgmt_response.status_code == 200:
                print("✅ Management session started successfully")
                try:
                    mgmt_result = mgmt_response.json()
                    print(f"Management response: {json.dumps(mgmt_result, indent=2)}")
                except:
                    print("Management response is not JSON")
            else:
                print(f"❌ Management session failed: {mgmt_response.status_code}")
                
        except Exception as e:
            print(f"❌ Management session request failed: {e}")

        # Step 4: Test Interface Access
        print("\n=== Step 4: Test Interface Access ===")
        interface_urls = [
            f"{base_url}/interfaces/ipv4",
            f"{base_url}/interfaces/vlans/ipv4",
            f"{base_url}/status"  # This one works for comparison
        ]
        
        for url in interface_urls:
            try:
                print(f"\nTesting: {url}")
                
                # Test with bearer token
                print("  Using Bearer token...")
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {bearer_token}"}
                )
                print(f"  Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"  Error: {response.text[:200]}...")
                else:
                    print(f"  Success: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"  ❌ Request failed: {e}")

        # Step 5: Test different authentication methods on interface endpoint
        print("\n=== Step 5: Test Different Auth Methods on Interface ===")
        test_url = f"{base_url}/interfaces/ipv4"
        
        # Test with digest auth (no bearer)
        print(f"\nTesting Digest Auth on {test_url}")
        try:
            response = await client.get(test_url, auth=httpx.DigestAuth(username, password))
            print(f"Digest Auth Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Digest Auth Error: {response.text[:200]}...")
        except Exception as e:
            print(f"Digest Auth failed: {e}")

        # Test with both digest and bearer
        print(f"\nTesting Both Auth Methods on {test_url}")
        try:
            response = await client.get(
                test_url, 
                auth=httpx.DigestAuth(username, password),
                headers={"Authorization": f"Bearer {bearer_token}"}
            )
            print(f"Both Auth Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Both Auth Error: {response.text[:200]}...")
            else:
                print(f"Both Auth Success: {response.text[:100]}...")
        except Exception as e:
            print(f"Both Auth failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_auth_flow())
