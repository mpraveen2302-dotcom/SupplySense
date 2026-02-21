ROLE_MAP = {
    "admin": ["ALL"],
    "planner": ["Control Tower","Analytics"],
    "warehouse": ["Control Tower"],
    "supplier": ["Analytics"]
}

def get_allowed_pages(role):
    return ROLE_MAP.get(role, [])
