#!/usr/bin/env python3
"""
Test script to reproduce the "unhashable type: 'list'" error
"""

from map_servers.duffel_server import search_flights_impl

def test_unhashable_error():
    """Test that reproduces the unhashable type error."""
    print("Testing for unhashable type error...")
    
    try:
        # Test the exact call from the error
        result = search_flights_impl(
            slices=[{
                'origin': 'BEY', 
                'destination': 'JED', 
                'departure_date': '2025-12-25'
            }],
            passengers=[{'type': 'adult'}]
        )
        print("✅ No unhashable type error occurred")
        return True
        
    except TypeError as e:
        if "unhashable type" in str(e):
            print(f"❌ UNHASHABLE TYPE ERROR: {e}")
            return False
        else:
            print(f"❌ Different TypeError: {e}")
            return False
    except Exception as e:
        print(f"⚠️  OTHER ERROR: {type(e).__name__}: {e}")
        return True

if __name__ == "__main__":
    print("=" * 50)
    print("TESTING FOR UNHASHABLE TYPE ERROR")
    print("=" * 50)
    test_unhashable_error()
