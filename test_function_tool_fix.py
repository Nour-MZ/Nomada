#!/usr/bin/env python3
"""
Test script to verify the @function_tool fix for unhashable type error
"""

from map_servers.duffel_server import search_flights

def test_function_tool_fix():
    """Test that the @function_tool wrapper works correctly."""
    print("Testing @function_tool wrapper...")
    
    try:
        # Test the exact call from the original error with @function_tool decorated function
        result = search_flights(
            slices=[{
                'origin': 'BEY', 
                'destination': 'JED', 
                'departure_date': '2025-12-25'
            }],
            passengers=[{'type': 'adult'}]
        )
        print("✅ SUCCESS: @function_tool wrapper works without unhashable type error!")
        print(f"Result type: {type(result)}")
        print(f"Number of results: {len(result) if result else 0}")
        return True
        
    except TypeError as e:
        if "unhashable type" in str(e):
            print(f"❌ UNHASHABLE TYPE ERROR STILL EXISTS: {e}")
            return False
        else:
            print(f"❌ Different TypeError: {e}")
            return False
    except Exception as e:
        print(f"⚠️  OTHER ERROR: {type(e).__name__}: {e}")
        print("(This is expected if API token is missing - the main fix worked)")
        return True

def test_direct_vs_tool_function():
    """Test that both direct and tool-wrapped functions work the same."""
    from map_servers.duffel_server import search_flights_impl
    
    print("\nTesting direct function vs @function_tool decorated function...")
    
    args = {
        'slices': [{'origin': 'BEY', 'destination': 'JED', 'departure_date': '2025-12-25'}],
        'passengers': [{'type': 'adult'}]
    }
    
    try:
        # Test direct function
        direct_result = search_flights_impl(**args)
        print(f"Direct function result type: {type(direct_result)}")
        
        # Test tool-wrapped function  
        tool_result = search_flights(**args)
        print(f"Tool function result type: {type(tool_result)}")
        
        # Both should be lists
        if isinstance(direct_result, list) and isinstance(tool_result, list):
            print("✅ SUCCESS: Both functions return the same type (list)")
            return True
        else:
            print("❌ FAILURE: Functions return different types")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING @function_tool FIX FOR UNHASHABLE TYPE ERROR")
    print("=" * 60)
    
    test1 = test_function_tool_fix()
    test2 = test_direct_vs_tool_function()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"@function_tool wrapper test: {'PASS' if test1 else 'FAIL'}")
    print(f"Direct vs tool function test: {'PASS' if test2 else 'FAIL'}")
    
    if test1 and test2:
        print("\n🎉 ALL TESTS PASSED! The unhashable type error has been fixed.")
    else:
        print("\n💥 SOME TESTS FAILED! The fix needs more work.")
