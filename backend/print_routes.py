from main import app

print("Registered Routes:")
for route in app.routes:
    # Some routes (like Mount) might not have methods
    methods = getattr(route, "methods", None)
    print(f"Path: {route.path}, Methods: {methods}")
