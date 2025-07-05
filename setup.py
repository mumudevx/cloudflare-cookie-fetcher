#!/usr/bin/env python3
"""
Setup script for Cloudflare Cookie Fetcher
"""

import subprocess
import sys
import os


def install_requirements():
    """Install required Python packages."""
    print("Installing Python requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Python requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        sys.exit(1)


def setup_camoufox():
    """Download and setup Camoufox browser."""
    print("Setting up Camoufox browser...")
    try:
        if os.name == 'nt':  # Windows
            subprocess.check_call(["camoufox", "fetch"])
        else:  # macOS/Linux
            subprocess.check_call([sys.executable, "-m", "camoufox", "fetch"])
        print("✓ Camoufox browser setup completed")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to setup Camoufox: {e}")
        sys.exit(1)


def main():
    """Main setup function."""
    print("Setting up Cloudflare Cookie Fetcher...")
    
    # Install Python requirements
    install_requirements()
    
    # Setup Camoufox
    setup_camoufox()
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    print("✓ Logs directory created")
    
    print("\n✓ Setup completed successfully!")
    print("\nUsage:")
    print("  python cloudflare_cookie_fetcher.py --username your@email.com --password yourpassword")
    print("  python cloudflare_cookie_fetcher.py  # Interactive mode")
    print("  python cloudflare_cookie_fetcher.py --headless  # Run in headless mode")


if __name__ == "__main__":
    main()