#!/usr/bin/env python3
"""
Generate development JWT token for testing.
"""

from trading_platform.services.auth_service import get_auth_service

def main():
    auth_service = get_auth_service()
    
    # Get admin user
    admin_user = auth_service.get_user_by_username("admin")
    if admin_user:
        token = auth_service.create_access_token(admin_user)
        print(f"Development token for admin user:")
        print(token)
    else:
        print("Admin user not found")

if __name__ == "__main__":
    main()