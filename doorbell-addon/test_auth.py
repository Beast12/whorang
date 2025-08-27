#!/usr/bin/env python3
"""
Test script to verify Home Assistant API authentication fix.
This simulates the addon environment and tests the camera discovery.
"""

import os
import sys
import requests
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ha_camera import HACameraManager
from config import Settings

def test_token_priority():
    """Test that supervisor token is prioritized over long-lived token."""
    print("Testing token priority...")
    
    # Mock settings with both tokens
    with patch('ha_camera.settings') as mock_settings:
        mock_settings.supervisor_token = "supervisor_test_token"
        mock_settings.hassio_token = None
        mock_settings.ha_access_token = "long_lived_test_token"
        
        manager = HACameraManager()
        
        # Check that supervisor token is used first
        expected_token = mock_settings.supervisor_token or mock_settings.ha_access_token
        actual_token = manager.supervisor_token or manager.ha_access_token
        
        print(f"Expected token: {expected_token}")
        print(f"Actual token: {actual_token}")
        
        assert actual_token == "supervisor_test_token", "Supervisor token should be prioritized"
        print("✓ Token priority test passed")

def test_api_call_structure():
    """Test that API calls use correct headers and endpoint."""
    print("\nTesting API call structure...")
    
    with patch('ha_camera.settings') as mock_settings, \
         patch('ha_camera.requests.get') as mock_get:
        
        mock_settings.supervisor_token = "test_supervisor_token"
        mock_settings.hassio_token = None
        mock_settings.ha_access_token = None
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "entity_id": "camera.front_door",
                "state": "idle",
                "attributes": {"friendly_name": "Front Door Camera"}
            }
        ]
        mock_get.return_value = mock_response
        
        manager = HACameraManager()
        cameras = manager.get_available_cameras()
        
        # Verify the API call was made correctly
        mock_get.assert_called_once_with(
            "http://supervisor/core/api/states",
            headers={
                "Authorization": "Bearer test_supervisor_token",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        print("✓ API call structure test passed")
        print(f"✓ Found {len(cameras)} camera entities")

def test_fallback_token():
    """Test fallback to long-lived token when supervisor token unavailable."""
    print("\nTesting token fallback...")
    
    with patch('ha_camera.settings') as mock_settings, \
         patch('ha_camera.requests.get') as mock_get:
        
        mock_settings.supervisor_token = None
        mock_settings.hassio_token = None
        mock_settings.ha_access_token = "fallback_long_lived_token"
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        manager = HACameraManager()
        cameras = manager.get_available_cameras()
        
        # Verify fallback token was used
        mock_get.assert_called_once_with(
            "http://supervisor/core/api/states",
            headers={
                "Authorization": "Bearer fallback_long_lived_token",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        print("✓ Token fallback test passed")

def test_no_token_handling():
    """Test behavior when no tokens are available."""
    print("\nTesting no token handling...")
    
    with patch('ha_camera.settings') as mock_settings:
        mock_settings.supervisor_token = None
        mock_settings.hassio_token = None
        mock_settings.ha_access_token = None
        
        manager = HACameraManager()
        cameras = manager.get_available_cameras()
        
        # Should return empty list when no tokens available
        assert cameras == [], "Should return empty list when no tokens available"
        print("✓ No token handling test passed")

if __name__ == "__main__":
    print("🔧 Testing Home Assistant API Authentication Fix")
    print("=" * 50)
    
    try:
        test_token_priority()
        test_api_call_structure()
        test_fallback_token()
        test_no_token_handling()
        
        print("\n" + "=" * 50)
        print("✅ All authentication tests passed!")
        print("\nKey fixes implemented:")
        print("• Added homeassistant_api: true to config.yaml")
        print("• Prioritize SUPERVISOR_TOKEN over long-lived token")
        print("• Correct API endpoint: http://supervisor/core/api/states")
        print("• Proper Bearer token authentication")
        print("• Fallback token handling")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
