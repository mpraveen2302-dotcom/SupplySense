ROLE_PERMISSIONS = {
    "admin": ["ALL"],
    "planner": ["Control Tower", "Analytics"],
    "warehouse": ["Control Tower"],
    "supplier": ["Analytics"]
}

def get_allowed_pages(role):
    return ROLE_PERMISSIONS.get(role, [])
