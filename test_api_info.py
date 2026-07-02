import sys
import os
from unittest.mock import MagicMock
from app import api_info

# Mock the request object globally for api_info to access
original_request = sys.modules['flask'].request if 'flask' in sys.modules else None
sys.modules['flask'].request = MagicMock()

# Mock jsonify directly as it's used in api_info
def mock_jsonify(data, status=200):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json = json_data
            self.status_code = status_code
        
        @property
        def status(self):
            return f"{self.status_code}"

    return MockResponse(json_data=data, status_code=status)
sys.modules['flask'].jsonify = mock_jsonify


try:
    # Test with a valid YouTube URL
    valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    sys.modules['flask'].request.args = {'url': valid_url}
    
    print(f"--- Testing /api/info with valid URL: {valid_url} ---")
    response_valid = api_info() # Call the actual function
    print("Valid URL Response:")
    print(f"Status: {response_valid.status}")
    print("Data:")
    print(response_valid.json)
    print("--------------------------------------------------\n")

except Exception as e:
    print(f"Error during valid URL test: {e}")
    import traceback
    traceback.print_exc()

finally:
    # Restore original request and jsonify to prevent interference with other imports
    if original_request: sys.modules['flask'].request = original_request
    if 'jsonify' in sys.modules['flask'].__dict__: del sys.modules['flask'].jsonify

print("--- Testing /api/info with missing URL ---")
try:
    # Test with a missing URL
    sys.modules['flask'].request.args = {}

    response_missing = api_info()
    print("Missing URL Response:")
    print(f"Status: {response_missing.status}")
    print("Data:")
    print(response_missing.json)
    print("--------------------------------------------------\n")
    
except Exception as e:
    print(f"Error during missing URL test: {e}")
    import traceback
    traceback.print_exc()
