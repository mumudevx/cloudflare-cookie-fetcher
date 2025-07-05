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
        
        # Screenshot settings
        self.screenshot_dir = "screenshots"
        self.step_counter = 0
        
        # Browser profile settings
        self.persistent_profile = os.getenv('PERSISTENT_PROFILE', 'true').lower() == 'true'
        self.profile_dir = os.getenv('PROFILE_DIRECTORY', 'browser_profile')
        
        self.logger = self._setup_logger()
        self._setup_screenshots()
        self._setup_browser_profile()
        
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
    
    def _setup_screenshots(self) -> None:
        """Set up screenshot directory and clean previous screenshots."""
        try:
            # Create screenshots directory
            os.makedirs(self.screenshot_dir, exist_ok=True)
            
            # Clean previous screenshots
            import glob
            screenshot_files = glob.glob(f"{self.screenshot_dir}/*.png")
            for file in screenshot_files:
                try:
                    os.remove(file)
                except:
                    pass
            
            self.logger.info(f"Screenshot directory prepared: {self.screenshot_dir}")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup screenshots: {str(e)}")
    
    def _setup_browser_profile(self) -> None:
        """Set up persistent browser profile directory."""
        try:
            # Create browser profile directory
            os.makedirs(self.profile_dir, exist_ok=True)
            self.logger.info(f"📁 Browser profile directory ready: {self.profile_dir}")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup browser profile: {str(e)}")
    
    def take_step_screenshot(self, page: Page, step_name: str) -> str:
        """Take a screenshot for a specific step."""
        try:
            self.step_counter += 1
            filename = f"step_{self.step_counter:02d}_{step_name}.png"
            screenshot_path = f"{self.screenshot_dir}/{filename}"
            page.screenshot(path=screenshot_path, full_page=True)
            self.logger.info(f"📸 Screenshot: {filename}")
            return screenshot_path
        except Exception as e:
            self.logger.error(f"Failed to take screenshot {step_name}: {str(e)}")
            return None
    
    def humanized_wait(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """Human-like random wait."""
        import random
        wait_time = random.uniform(min_seconds, max_seconds)
        self.logger.info(f"⏳ Humanized wait: {wait_time:.1f}s")
        import time
        time.sleep(wait_time)
    
    def check_login_status(self, page: Page) -> bool:
        """Check if user is already logged in to Cloudflare."""
        try:
            self.logger.info("🔍 Checking current login status")
            
            # Multiple indicators of being logged in
            login_indicators = [
                '[data-testid="user-menu-button"]',
                '[data-testid="user-dropdown"]',
                '.user-menu',
                '.account-menu',
                'button[aria-label*="account"]',
                'button[aria-label*="user"]',
                'div[data-testid*="user"]',
                'nav[data-testid*="user"]',
                # Dashboard specific elements
                '[data-testid="dashboard"]',
                '.dashboard',
                'main[role="main"]',
                '[data-testid="zone-list"]'
            ]
            
            for indicator in login_indicators:
                try:
                    if page.locator(indicator).count() > 0 and page.locator(indicator).first.is_visible():
                        self.logger.info(f"✅ Found login indicator: {indicator}")
                        return True
                except:
                    continue
            
            # Also check URL for dashboard patterns
            current_url = page.url
            if ('dash.cloudflare.com' in current_url and 
                not ('login' in current_url.lower() or 'sign-in' in current_url.lower())):
                if ('dashboard' in current_url or 'overview' in current_url or 
                    current_url.endswith('dash.cloudflare.com/') or
                    '/zones/' in current_url):
                    self.logger.info("✅ Login detected from URL pattern")
                    return True
            
            # Check if we're on login page (not logged in)
            if 'login' in current_url.lower() or 'sign-in' in current_url.lower():
                self.logger.info("❌ Currently on login page - not logged in")
                return False
            
            self.logger.info("❓ Login status unclear - assuming not logged in")
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking login status: {str(e)}")
            return False
    
    def navigate_to_cloudflare(self, page: Page) -> None:
        """Navigate to Cloudflare dashboard."""
        try:
            self.logger.info("🌐 Navigating to Cloudflare dashboard")
            page.goto("https://dash.cloudflare.com", timeout=self.timeout)
            
            # Wait for page to load
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            self.take_step_screenshot(page, "navigate_to_cloudflare")
            
            # Humanized wait after navigation
            self.humanized_wait(2.0, 4.0)
            
            self.logger.info("✅ Successfully navigated to Cloudflare dashboard")
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate to Cloudflare: {str(e)}")
            raise
    
    def handle_cloudflare_challenge(self, page: Page) -> None:
        """Handle Cloudflare challenge if present."""
        try:
            self.logger.info("🔍 Checking for Cloudflare challenge")
            
            # Wait for potential challenge to appear
            self.humanized_wait(3.0, 5.0)
            self.take_step_screenshot(page, "check_cloudflare_challenge")
            
            # Check for common Cloudflare challenge indicators
            challenge_selectors = [
                '[data-ray]',  # Cloudflare Ray ID
                '.cf-browser-verification',
                '.cf-checking-browser',
                '#cf-spinner-please-wait'
            ]
            
            for selector in challenge_selectors:
                if page.locator(selector).is_visible():
                    self.logger.info("🛡️ Cloudflare challenge detected, waiting for resolution")
                    self.take_step_screenshot(page, "cloudflare_challenge_detected")
                    
                    # Wait for challenge to resolve
                    page.wait_for_selector(selector, state="hidden", timeout=self.challenge_timeout * 1000)
                    page.wait_for_load_state("networkidle", timeout=self.timeout)
                    
                    self.take_step_screenshot(page, "cloudflare_challenge_resolved")
                    self.logger.info("✅ Cloudflare challenge resolved")
                    return
            
            self.logger.info("ℹ️ No Cloudflare challenge detected")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error handling Cloudflare challenge: {str(e)}")
            self.take_step_screenshot(page, "cloudflare_challenge_error")
            # Continue anyway as challenge might have resolved
    
    
    def fill_login_credentials(self, page: Page, username: str, password: str) -> None:
        """Fill login credentials without submitting the form."""
        try:
            self.logger.info("✏️ Filling login credentials")
            self.take_step_screenshot(page, "before_filling_credentials")
            
            # Look for login form
            login_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                '#email'
            ]
            
            email_input = None
            for selector in login_selectors:
                try:
                    if page.locator(selector).count() > 0 and page.locator(selector).is_visible():
                        email_input = page.locator(selector).first
                        break
                except:
                    continue
            
            if not email_input:
                self.logger.error("❌ Could not find email input field")
                raise Exception("Email input field not found")
            
            # Fill email with humanized input
            self.logger.info("✏️ Filling email field")
            self.humanized_wait(1.0, 2.0)
            email_input.click()
            self.humanized_wait(0.5, 1.0)
            email_input.fill(username)
            self.take_step_screenshot(page, "email_filled")
            self.humanized_wait(1.0, 2.0)
            
            # Find password field
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password'
            ]
            
            password_input = None
            for selector in password_selectors:
                try:
                    if page.locator(selector).count() > 0 and page.locator(selector).is_visible():
                        password_input = page.locator(selector).first
                        break
                except:
                    continue
            
            if not password_input:
                self.logger.error("❌ Could not find password input field")
                raise Exception("Password input field not found")
            
            # Fill password with humanized input
            self.logger.info("✏️ Filling password field")
            password_input.click()
            self.humanized_wait(0.5, 1.0)
            password_input.fill(password)
            self.take_step_screenshot(page, "credentials_filled")
            self.humanized_wait(1.0, 2.0)
            
            
            self.logger.info("✅ Credentials filled successfully - ready for manual login")
            self.take_step_screenshot(page, "ready_for_manual_login")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to fill credentials: {str(e)}")
            raise
    
    def perform_login(self, page: Page, username: str, password: str) -> None:
        """Perform login to Cloudflare with humanized flow."""
        try:
            self.logger.info("🔐 Attempting to login to Cloudflare")
            self.take_step_screenshot(page, "login_page_loaded")
            
            # Check if already logged in
            if page.locator('[data-testid="user-menu-button"]').is_visible():
                self.logger.info("✅ Already logged in to Cloudflare")
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
            
            # Fill login form with humanized input
            self.logger.info("✏️ Filling login credentials")
            self.humanized_wait(1.0, 2.0)
            
            # Humanized email input
            email_input.click()
            self.humanized_wait(0.5, 1.0)
            email_input.fill(username)
            self.take_step_screenshot(page, "email_filled")
            self.humanized_wait(1.0, 2.0)
            
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
                self.logger.error("❌ Could not find password input field")
                raise Exception("Password input field not found")
            
            # Humanized password input
            password_input.click()
            self.humanized_wait(0.5, 1.0)
            password_input.fill(password)
            self.take_step_screenshot(page, "password_filled")
            self.humanized_wait(1.0, 2.0)
            
            
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
                self.logger.error("❌ Could not find enabled submit button")
                self.take_step_screenshot(page, "submit_button_not_found")
                raise Exception("Submit button not found or disabled")
            
            self.logger.info("🚀 Submitting login form")
            self.take_step_screenshot(page, "before_submit_click")
            
            # Humanized submit button click
            submit_button.hover()
            self.humanized_wait(0.5, 1.0)
            submit_button.click()
            
            # Take screenshot immediately after click
            self.take_step_screenshot(page, "after_submit_click")
            
            # Wait for login to complete with longer timeout
            self.logger.info("⏳ Waiting for login to complete...")
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            self.humanized_wait(3.0, 5.0)  # Additional wait for page to fully load
            
            self.take_step_screenshot(page, "after_login_attempt")
            
            # Verify login success with enhanced checks
            self.logger.info("🔍 Verifying login success...")
            
            # Take screenshot for verification analysis
            self.take_step_screenshot(page, "login_verification_check")
            
            # Wait for page to load after login
            self.humanized_wait(3.0, 5.0)
            
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
                'main[role="main"]',  # Main content area
                '[data-testid="zone-list"]',  # Domain list
                # URL-based check
                'body'  # We'll check URL separately
            ]
            
            login_success = False
            found_indicator = None
            
            for selector in success_selectors:
                try:
                    if page.locator(selector).count() > 0 and page.locator(selector).first.is_visible():
                        self.logger.info(f"✅ Login success indicator found: {selector}")
                        found_indicator = selector
                        login_success = True
                        break
                except:
                    continue
            
            # Also check URL for dashboard
            current_url = page.url
            self.logger.info(f"🌐 Current URL: {current_url}")
            
            if 'dash.cloudflare.com' in current_url and not ('login' in current_url.lower() or 'sign-in' in current_url.lower()):
                if 'dashboard' in current_url or 'overview' in current_url or current_url.endswith('dash.cloudflare.com/'):
                    self.logger.info("✅ Login success detected from URL pattern")
                    login_success = True
            
            # Check if we're still on login page (failure indicator)
            if 'login' in current_url.lower() or 'sign-in' in current_url.lower():
                self.logger.warning("⚠️ Still on login page - login may have failed")
                login_success = False
            
            # Take final verification screenshot
            self.take_step_screenshot(page, "login_verification_result")
            
            if login_success:
                self.logger.info(f"✅ Successfully logged in to Cloudflare (indicator: {found_indicator or 'URL pattern'})")
                self.take_step_screenshot(page, "login_success_confirmed")
            else:
                self.logger.error(f"❌ Login verification failed - Current URL: {current_url}")
                self.take_step_screenshot(page, "login_failed")
                # STOP here instead of continuing - don't extract cookies without proper login
                raise Exception(f"Login failed - still on login page: {current_url}")
                
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
            
            # Prepare browser options (no persistent profile in launch)
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
            
            # Storage state file for persistence
            storage_state_file = os.path.join(self.profile_dir, 'storage_state.json')
            
            with Camoufox(**browser_options) as browser:
                # Create context with storage state if available
                context_options = {}
                
                if self.persistent_profile and os.path.exists(storage_state_file):
                    try:
                        context_options['storage_state'] = storage_state_file
                        self.logger.info(f"🔧 Loading browser state from: {storage_state_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load storage state: {str(e)}")
                        context_options = {}
                else:
                    self.logger.info("🔧 Starting fresh browser session")
                
                # Create context and page
                if context_options:
                    context = browser.new_context(**context_options)
                    page = context.new_page()
                else:
                    page = browser.new_page()
                
                # Step 1: Navigate to Cloudflare
                self.navigate_to_cloudflare(page)
                
                # Step 2: Check if login is required
                already_logged_in = self.check_login_status(page)
                
                if not already_logged_in:
                    self.logger.info("🔐 Login required - starting authentication process")
                    
                    # Handle Cloudflare challenge
                    self.handle_cloudflare_challenge(page)
                    
                    # Step 3: Fill credentials if provided
                    if self.username and self.password:
                        self.logger.info("✏️ Filling login credentials for manual submission")
                        self.fill_login_credentials(page, self.username, self.password)
                        
                        # Wait for manual login
                        self.logger.info("⏳ Please manually click the login button and complete authentication")
                        self.logger.info("📝 The script will wait for you to complete login...")
                        
                        # Wait for login completion (up to 5 minutes)
                        login_timeout = 300  # 5 minutes
                        login_completed = False
                        
                        for i in range(login_timeout):
                            self.humanized_wait(1.0, 1.0)  # Check every second
                            
                            if self.check_login_status(page):
                                self.logger.info("✅ Manual login completed successfully!")
                                login_completed = True
                                break
                            
                            # Log progress every 30 seconds
                            if i % 30 == 0 and i > 0:
                                self.logger.info(f"⏳ Still waiting for login... ({i}/{login_timeout}s)")
                        
                        if not login_completed:
                            self.logger.error("❌ Login timeout - please try again")
                            raise Exception("Manual login timeout")
                            
                    else:
                        self.logger.error("❌ No credentials provided in .env file")
                        raise Exception("Login credentials required but not provided")
                        
                    # Save storage state after successful login
                    if self.persistent_profile:
                        try:
                            os.makedirs(self.profile_dir, exist_ok=True)
                            page.context.storage_state(path=storage_state_file)
                            self.logger.info(f"💾 Login session saved to: {storage_state_file}")
                        except Exception as e:
                            self.logger.warning(f"Failed to save storage state: {str(e)}")
                            
                else:
                    self.logger.info("🎉 Already logged in - using existing session")
                
                # Step 4: Extract cookies
                self.logger.info("🍪 Extracting cookies...")
                cookies = self.extract_cookies(page)
                
                # Step 5: Save cookies to file
                self.save_cookies_to_file(cookies)
                
                # Final success screenshot
                self.take_step_screenshot(page, "final_success")
                
                self.logger.info("✅ Cloudflare cookie fetching completed successfully")
                
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