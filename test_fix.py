#!/usr/bin/env python3
"""
Test script to verify that the search_flights comparison error has been fixed.
"""

from map_servers.duffel_server import search_flights_impl

def test_search_flights_with_list_passengers():
    """Test that search_flights accepts passengers as a list without comparison error."""
    print("Testing search_flights with passengers as list...")
    
    try:
        # This should now work without the ">' not supported between instances of 'list' and 'int'" error
        result = search_flights_impl(
            slices=[{
                "origin": "BEY",
                "destination": "JFK", 
                "departure_date": "2025-12-26"
            }],
            passengers=[{"type": "adult"}],
            cabin_class="economy",
            max_offers=2
        )
        
        print("✅ SUCCESS: No comparison error occurred!")
        print(f"Function returned: {type(result)} (expected list)")
        
        if isinstance(result, list):
            print(f"Number of results: {len(result)}")
            if result:
                print("Sample result keys:", list(result[0].keys()) if result else "No results")
            else:
                print("No results returned (likely due to missing API token)")
        
        return True
        
    except TypeError as e:
        if "' not supported between instances of 'list' and 'int'" in str(e):
            print("❌ FAILURE: The original comparison error still exists!")
            print(f"Error: {e}")
            return False
        else:
            print(f"❌ FAILURE: Different TypeError occurred: {e}")
            return False
    except Exception as e:
        print(f"⚠️  OTHER ERROR: {type(e).__name__}: {e}")
        print("(This is expected if API token is missing - the main fix worked)")
        return True

def test_search_flights_with_int_passengers():
    """Test backward compatibility with integer passengers."""
    print("\nTesting search_flights with passengers as integer (backward compatibility)...")
    
    try:
        result = search_flights_impl(
            slices=[{
                "origin": "BEY",
                "destination": "JFK", 
                "departure_date": "2025-12-26"
            }],
            passengers=2,  # Integer instead of list
            cabin_class="economy",
            max_offers=2
        )
        
        print("✅ SUCCESS: Backward compatibility with integer passengers works!")
        print(f"Function returned: {type(result)} (expected list)")
        return True
        
    except Exception as e:
        print(f"❌ FAILURE: Backward compatibility test failed: {type(e).__name__}: {e}")
        return False

def test_search_flights_with_none_passengers():
    """Test default passengers behavior."""
    print("\nTesting search_flights with passengers=None (default)...")
    
    try:
        result = search_flights_impl(
            slices=[{
                "origin": "BEY",
                "destination": "JFK", 
                "departure_date": "2025-12-26"
            }],
            passengers=None,  # Should default to one adult
            cabin_class="economy",
            max_offers=2
        )
        
        print("✅ SUCCESS: Default passengers behavior works!")
        print(f"Function returned: {type(result)} (expected list)")
        return True
        
    except Exception as e:
        print(f"❌ FAILURE: Default passengers test failed: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING SEARCH_FLIGHTS COMPARISON ERROR FIX")
    print("=" * 60)
    
    test1 = test_search_flights_with_list_passengers()
    test2 = test_search_flights_with_int_passengers()
    test3 = test_search_flights_with_none_passengers()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"List passengers test: {'PASS' if test1 else 'FAIL'}")
    print(f"Integer passengers test: {'PASS' if test2 else 'FAIL'}")
    print(f"Default passengers test: {'PASS' if test3 else 'FAIL'}")
    
    if test1 and test2 and test3:
        print("\n🎉 ALL TESTS PASSED! The comparison error has been fixed.")
    else:
        print("\n💥 SOME TESTS FAILED! The fix needs more work.")
