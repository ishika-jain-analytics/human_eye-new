#!/usr/bin/env python3
"""
Flask Route Debugger
Lists all available Flask routes and their endpoints for debugging url_for() issues.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    import app

    print("🔍 Flask Route Debugger")
    print("=" * 50)
    print("Available Flask Routes:")
    print("-" * 30)

    routes = []
    for rule in app.app.url_map.iter_rules():
        routes.append((rule.endpoint, rule.rule, ', '.join(rule.methods - {'HEAD', 'OPTIONS'})))

    # Sort by endpoint name for easier reading
    routes.sort(key=lambda x: x[0])

    for endpoint, rule, methods in routes:
        print(f"{endpoint:<20} {rule:<25} [{methods}]")

    print("\n" + "=" * 50)
    print("✅ Route debugging complete!")
    print("\nUsage tips:")
    print("- Use url_for('endpoint_name') in your code")
    print("- Endpoint names match your function names")
    print("- Example: url_for('predict') for def predict()")

except ImportError as e:
    print(f"❌ Error importing app: {e}")
    print("Make sure you're running this from the project root directory")

except Exception as e:
    print(f"❌ Error: {e}")