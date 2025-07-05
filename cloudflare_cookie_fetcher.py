#!/usr/bin/env python3
"""
Cloudflare Cookie Fetcher
Automates login to Cloudflare and extracts cookies for a domain.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from camoufox import Camoufox
from playwright.sync_api import Page, Browser
from dotenv import load_dotenv


class CloudflareCookieFetcher:
    """Main class for fetching Cloudflare cookies."""
    
    def __init__(self):
        """Initialize the cookie fetcher with environment variables."""
        # Load environment variables
        load_dotenv()
        
        # Browser settings
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        self.humanize = os.getenv('HUMANIZE', 'true').lower() == 'true'
        self.timeout = int(os.getenv('TIMEOUT', '30000'))
        
        # Cloudflare credentials
        self.username = os.getenv('CLOUDFLARE_USERNAME')
        self.password = os.getenv('CLOUDFLARE_PASSWORD')
        
        # Output settings
        self.cookies_filename = os.getenv('COOKIES_FILENAME', 'cf-cookies.txt')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Proxy settings
        self.http_proxy = os.getenv('HTTP_PROXY')
        self.https_proxy = os.getenv('HTTPS_PROXY')
        
        # Advanced settings
        self.challenge_timeout = int(os.getenv('CHALLENGE_TIMEOUT', '30'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '5'))
        
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('cloudflare_cookie_fetcher')
        logger.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create file handler with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/cloudflare_cookies_{timestamp}.json'
        
        # Create a custom formatter for JSON logging
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                return json.dumps(log_entry)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        
        # Also add console handler for immediate feedback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def navigate_to_cloudflare(self, page: Page) -> None:
        """Navigate to Cloudflare dashboard."""
        try:
            self.logger.info("Navigating to Cloudflare dashboard")
            page.goto("https://dash.cloudflare.com", timeout=self.timeout)
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            self.logger.info("Successfully navigated to Cloudflare dashboard")
        except Exception as e:
            self.logger.error(f"Failed to navigate to Cloudflare: {str(e)}")
            raise
    
    def handle_cloudflare_challenge(self, page: Page) -> None:
        """Handle Cloudflare challenge if present."""
        try:
            self.logger.info("Checking for Cloudflare challenge")
            
            # Wait for potential challenge to appear
            page.wait_for_timeout(3000)
            
            # Check for common Cloudflare challenge indicators
            challenge_selectors = [
                '[data-ray]',  # Cloudflare Ray ID
                '.cf-browser-verification',
                '.cf-checking-browser',
                '#cf-spinner-please-wait'
            ]
            
            for selector in challenge_selectors:
                if page.locator(selector).is_visible():
                    self.logger.info("Cloudflare challenge detected, waiting for resolution")
                    # Wait for challenge to resolve
                    page.wait_for_selector(selector, state="hidden", timeout=self.challenge_timeout * 1000)
                    page.wait_for_load_state("networkidle", timeout=self.timeout)
                    self.logger.info("Cloudflare challenge resolved")
                    return
            
            self.logger.info("No Cloudflare challenge detected")
            
        except Exception as e:
            self.logger.warning(f"Error handling Cloudflare challenge: {str(e)}")
            # Continue anyway as challenge might have resolved
    
    def handle_human_verification(self, page: Page) -> None:
        """Handle human verification checkbox before login with mouse movement."""
        try:
            self.logger.info("Checking for human verification checkbox")
            
            # Extended selectors for human verification
            verification_selectors = [
                'input[type="checkbox"]',
                '[role="checkbox"]',
                '.cf-turnstile',
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[src*="turnstile"]',
                '[data-testid*="checkbox"]',
                '[data-cy*="checkbox"]',
                '.checkbox',
                'label:has(input[type="checkbox"])',
                'div:has(input[type="checkbox"])'
            ]
            
            # Wait for verification to load
            page.wait_for_timeout(3000)
            
            # Check for verification checkbox
            verification_found = False
            for selector in verification_selectors:
                try:
                    checkbox = page.locator(selector)
                    if checkbox.count() > 0 and checkbox.first.is_visible():
                        self.logger.info(f"Found human verification element: {selector}")
                        
                        # If it's an iframe (Turnstile), handle it differently
                        if 'iframe' in selector.lower() or 'turnstile' in selector.lower():
                            self.logger.info("Detected Turnstile verification iframe")
                            # Wait for Turnstile to load and complete automatically
                            page.wait_for_timeout(8000)
                            
                            # Check if verification completed
                            success_selectors = [
                                '.cf-turnstile-success',
                                '[data-cf-turnstile-success]',
                                'iframe[src*="turnstile"] + [style*="display: none"]'
                            ]
                            
                            for success_selector in success_selectors:
                                if page.locator(success_selector).count() > 0:
                                    self.logger.info("Turnstile verification completed automatically")
                                    verification_found = True
                                    break
                        else:
                            # Regular checkbox - use mouse movement and click
                            try:
                                # Get the checkbox element
                                checkbox_element = checkbox.first
                                
                                # Check if it's already checked
                                if checkbox_element.is_checked():
                                    self.logger.info("Checkbox already checked")
                                    verification_found = True
                                else:
                                    # Get bounding box for mouse movement
                                    bbox = checkbox_element.bounding_box()
                                    if bbox:
                                        # Calculate center point
                                        center_x = bbox['x'] + bbox['width'] / 2
                                        center_y = bbox['y'] + bbox['height'] / 2
                                        
                                        self.logger.info(f"Moving mouse to checkbox at ({center_x}, {center_y})")
                                        
                                        # Humanized mouse movement
                                        page.mouse.move(center_x, center_y)
                                        page.wait_for_timeout(500)  # Small delay
                                        
                                        # Click the checkbox
                                        self.logger.info("Clicking verification checkbox with mouse")
                                        page.mouse.click(center_x, center_y)
                                        page.wait_for_timeout(1000)
                                        
                                        # Verify click was successful
                                        if checkbox_element.is_checked():
                                            self.logger.info("Checkbox successfully checked")
                                            verification_found = True
                                        else:
                                            # Try alternative click method
                                            self.logger.info("Trying alternative click method")
                                            checkbox_element.click(force=True)
                                            page.wait_for_timeout(500)
                                            
                                            if checkbox_element.is_checked():
                                                self.logger.info("Checkbox checked with alternative method")
                                                verification_found = True
                                    else:
                                        # Fallback to regular click
                                        self.logger.info("Using fallback click method")
                                        checkbox_element.click(force=True)
                                        page.wait_for_timeout(1000)
                                        verification_found = True
                                        
                            except Exception as click_error:
                                self.logger.warning(f"Click error: {str(click_error)}")
                                continue
                        
                        if verification_found:
                            break
                        
                except Exception as selector_error:
                    self.logger.debug(f"Selector error for {selector}: {str(selector_error)}")
                    continue
            
            if verification_found:
                self.logger.info("Human verification handled successfully")
                # Wait for any additional processing
                page.wait_for_timeout(3000)
            else:
                self.logger.info("No human verification checkbox found")
                
        except Exception as e:
            self.logger.warning(f"Error handling human verification: {str(e)}")
            # Continue anyway as verification might not be required
    
    def perform_login(self, page: Page, username: str, password: str) -> None:
        """Perform login to Cloudflare."""
        try:
            self.logger.info("Attempting to login to Cloudflare")
            
            # Check if already logged in
            if page.locator('[data-testid="user-menu-button"]').is_visible():
                self.logger.info("Already logged in to Cloudflare")
                return
            
            # Look for login form
            login_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                '#email'
            ]
            
            email_input = None
            for selector in login_selectors:
                if page.locator(selector).is_visible():
                    email_input = page.locator(selector)
                    break
            
            if not email_input:
                self.logger.error("Could not find email input field")
                raise Exception("Email input field not found")
            
            # Fill login form
            self.logger.info("Filling login credentials")
            email_input.fill(username)
            
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password'
            ]
            
            password_input = None
            for selector in password_selectors:
                if page.locator(selector).is_visible():
                    password_input = page.locator(selector)
                    break
            
            if not password_input:
                self.logger.error("Could not find password input field")
                raise Exception("Password input field not found")
            
            password_input.fill(password)
            
            # Handle human verification checkbox before submitting
            self.handle_human_verification(page)
            
            # Submit login form - try different approaches
            submit_button = None
            
            # First try: Look for submit button by type
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    locator = page.locator(selector)
                    if locator.count() > 0 and locator.first.is_visible() and not locator.first.is_disabled():
                        submit_button = locator.first
                        self.logger.info(f"Found submit button: {selector}")
                        break
                except:
                    continue
            
            # Second try: Look for specific login buttons
            if not submit_button:
                login_button_selectors = [
                    'button:has-text("Log in"):not(:has-text("Google")):not(:has-text("Apple"))',
                    'button:has-text("Sign in"):not(:has-text("Google")):not(:has-text("Apple"))',
                    'button:has-text("Continue"):not(:has-text("Google")):not(:has-text("Apple"))'
                ]
                
                for selector in login_button_selectors:
                    try:
                        locator = page.locator(selector)
                        if locator.count() > 0 and locator.first.is_visible() and not locator.first.is_disabled():
                            submit_button = locator.first
                            self.logger.info(f"Found login button: {selector}")
                            break
                    except:
                        continue
            
            # Third try: Look for any button in form context
            if not submit_button:
                form_button_selectors = [
                    'form button:not(:has-text("Google")):not(:has-text("Apple"))',
                    'form input[type="submit"]',
                    '[role="button"]:not(:has-text("Google")):not(:has-text("Apple"))'
                ]
                
                for selector in form_button_selectors:
                    try:
                        locator = page.locator(selector)
                        if locator.count() > 0 and locator.first.is_visible() and not locator.first.is_disabled():
                            submit_button = locator.first
                            self.logger.info(f"Found form button: {selector}")
                            break
                    except:
                        continue
            
            if not submit_button:
                self.logger.error("Could not find enabled submit button")
                raise Exception("Submit button not found or disabled")
            
            self.logger.info("Submitting login form")
            submit_button.click()
            
            # Wait for login to complete
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            
            # Verify login success with multiple checks
            self.logger.info("Verifying login success...")
            
            # Wait for page to load after login
            page.wait_for_timeout(5000)
            
            # Multiple success indicators
            success_selectors = [
                '[data-testid="user-menu-button"]',
                '[data-testid="user-dropdown"]',
                '.user-menu',
                '.account-menu',
                'button[aria-label*="account"]',
                'button[aria-label*="user"]',
                'div[data-testid*="user"]',
                'nav[data-testid*="user"]',
                # Dashboard indicators
                'h1:has-text("Cloudflare")',
                '[data-testid="dashboard"]',
                '.dashboard',
                # URL-based check
                'body'  # We'll check URL separately
            ]
            
            login_success = False
            for selector in success_selectors:
                try:
                    if page.locator(selector).count() > 0 and page.locator(selector).first.is_visible():
                        self.logger.info(f"Login success indicator found: {selector}")
                        login_success = True
                        break
                except:
                    continue
            
            # Also check URL for dashboard
            current_url = page.url
            if 'dash.cloudflare.com' in current_url and ('dashboard' in current_url or 'overview' in current_url):
                self.logger.info("Login success detected from URL")
                login_success = True
            
            # Check if we're still on login page (failure indicator)
            if 'login' in current_url.lower() or 'sign-in' in current_url.lower():
                self.logger.warning("Still on login page - login may have failed")
                login_success = False
            
            if login_success:
                self.logger.info("Successfully logged in to Cloudflare")
            else:
                self.logger.error(f"Login verification failed - Current URL: {current_url}")
                # Don't raise exception immediately, let's try to continue
                self.logger.warning("Continuing with cookie extraction despite login verification failure")
                
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            raise
    
    def extract_cookies(self, page: Page) -> List[Dict]:
        """Extract cookies from the current page."""
        try:
            self.logger.info("Extracting cookies from Cloudflare")
            
            # Get all cookies for the current domain
            cookies = page.context.cookies()
            
            # Filter for Cloudflare domain cookies
            cloudflare_cookies = [
                cookie for cookie in cookies 
                if 'cloudflare.com' in cookie.get('domain', '')
            ]
            
            self.logger.info(f"Extracted {len(cloudflare_cookies)} Cloudflare cookies")
            
            return cloudflare_cookies
            
        except Exception as e:
            self.logger.error(f"Failed to extract cookies: {str(e)}")
            raise
    
    def save_cookies_to_file(self, cookies: List[Dict]) -> None:
        """Save cookies to a text file in curl -b format."""
        try:
            self.logger.info(f"Saving cookies to {self.cookies_filename}")
            
            # Filter for cloudflare.com cookies only
            cloudflare_cookies = [
                cookie for cookie in cookies 
                if 'cloudflare.com' in cookie.get('domain', '')
            ]
            
            with open(self.cookies_filename, 'w', encoding='utf-8') as f:
                f.write("# Cloudflare Cookies - curl -b format\n")
                f.write(f"# Generated on: {datetime.now().isoformat()}\n")
                f.write("# Usage: curl -b \"$(cat cf-cookies.txt)\" https://dash.cloudflare.com/api/v4/graphql\n\n")
                
                # Create curl -b format: name=value; name2=value2; ...
                cookie_pairs = []
                for cookie in cloudflare_cookies:
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    if name and value:
                        cookie_pairs.append(f"{name}={value}")
                
                # Write cookies in curl -b format
                if cookie_pairs:
                    cookies_string = '; '.join(cookie_pairs)
                    f.write(cookies_string)
                    f.write('\n')
                else:
                    f.write("# No Cloudflare cookies found\n")
                
                # Also write individual cookies for reference
                f.write("\n# Individual cookies (for reference):\n")
                for cookie in cloudflare_cookies:
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    domain = cookie.get('domain', '')
                    path = cookie.get('path', '/')
                    secure = cookie.get('secure', False)
                    expires = cookie.get('expires', -1)
                    
                    f.write(f"# {name}={value} (domain: {domain}, path: {path}, secure: {secure}, expires: {expires})\n")
            
            self.logger.info(f"Successfully saved {len(cloudflare_cookies)} Cloudflare cookies to {self.cookies_filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {str(e)}")
            raise
    
    def run(self) -> None:
        """Run the complete cookie fetching process."""
        try:
            self.logger.info("Starting Cloudflare cookie fetcher")
            
            # Prepare browser options
            browser_options = {
                'headless': self.headless,
                'humanize': self.humanize
            }
            
            # Add proxy settings if configured
            if self.http_proxy or self.https_proxy:
                browser_options['proxy'] = {}
                if self.http_proxy:
                    browser_options['proxy']['http'] = self.http_proxy
                if self.https_proxy:
                    browser_options['proxy']['https'] = self.https_proxy
            
            with Camoufox(**browser_options) as browser:
                page = browser.new_page()
                
                # Step 1: Navigate to Cloudflare
                self.navigate_to_cloudflare(page)
                
                # Step 2: Handle Cloudflare challenge
                self.handle_cloudflare_challenge(page)
                
                # Step 3: Login if credentials provided
                if self.username and self.password:
                    self.perform_login(page, self.username, self.password)
                else:
                    self.logger.info("No credentials provided in .env file, skipping login")
                
                # Step 4: Extract cookies
                cookies = self.extract_cookies(page)
                
                # Step 5: Save cookies to file
                self.save_cookies_to_file(cookies)
                
                self.logger.info("Cloudflare cookie fetching completed successfully")
                
        except Exception as e:
            self.logger.error(f"Cookie fetching failed: {str(e)}")
            raise


def main():
    """Main entry point."""
    print("🦊 Cloudflare Cookie Fetcher")
    print("============================")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please create a .env file with your configuration.")
        print("You can copy the example .env file and update it with your settings.")
        sys.exit(1)
    
    # Create and run fetcher
    try:
        fetcher = CloudflareCookieFetcher()
        
        # Show configuration summary
        print(f"📊 Configuration:")
        print(f"   - Headless mode: {fetcher.headless}")
        print(f"   - Humanize: {fetcher.humanize}")
        print(f"   - Timeout: {fetcher.timeout}ms")
        print(f"   - Output file: {fetcher.cookies_filename}")
        print(f"   - Log level: {fetcher.log_level}")
        
        if fetcher.username:
            print(f"   - Username: {fetcher.username}")
        else:
            print("   - Username: Not configured (will skip login)")
        
        if fetcher.http_proxy or fetcher.https_proxy:
            print(f"   - Proxy: Configured")
        
        print("\n🚀 Starting cookie extraction...")
        
        fetcher.run()
        print(f"✅ Cookies successfully extracted and saved to {fetcher.cookies_filename}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()