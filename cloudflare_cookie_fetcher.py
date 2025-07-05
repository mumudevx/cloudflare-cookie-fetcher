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
    
    def simulate_human_mouse_movement(self, page: Page, target_x: int, target_y: int) -> None:
        """Simulate human-like mouse movement to target coordinates."""
        try:
            import random
            import math
            
            # Get current mouse position (start from a random position)
            current_x = random.randint(100, 400)
            current_y = random.randint(100, 300)
            
            # Calculate distance and steps
            distance = math.sqrt((target_x - current_x) ** 2 + (target_y - current_y) ** 2)
            steps = max(10, int(distance / 20))  # More steps for longer distances
            
            # Move mouse in curved path with random variations
            for i in range(steps):
                progress = i / steps
                
                # Add some curve to the movement
                curve_offset = math.sin(progress * math.pi) * random.uniform(-20, 20)
                
                # Calculate intermediate position with curve
                intermediate_x = current_x + (target_x - current_x) * progress + curve_offset
                intermediate_y = current_y + (target_y - current_y) * progress
                
                # Add small random variations
                intermediate_x += random.uniform(-3, 3)
                intermediate_y += random.uniform(-3, 3)
                
                # Move mouse to intermediate position
                page.mouse.move(intermediate_x, intermediate_y)
                
                # Random delay between movements
                import time
                time.sleep(random.uniform(0.01, 0.03))
            
            # Final precise movement to target
            page.mouse.move(target_x, target_y)
            
        except Exception as e:
            self.logger.debug(f"Mouse movement simulation failed: {str(e)}")
            # Fallback to direct movement
            page.mouse.move(target_x, target_y)
    
    def _try_hover_focus_click(self, element) -> None:
        """Try hover, focus, and click sequence."""
        element.hover()
        self.humanized_wait(0.2, 0.5)
        element.focus()
        self.humanized_wait(0.1, 0.3)
        element.click()
    
    def _try_coordinate_click(self, frame, element) -> None:
        """Try clicking using exact coordinates."""
        bbox = element.bounding_box()
        if bbox:
            import random
            center_x = bbox['x'] + bbox['width'] / 2 + random.uniform(-2, 2)
            center_y = bbox['y'] + bbox['height'] / 2 + random.uniform(-2, 2)
            frame.mouse.click(center_x, center_y)
    
    def _check_challenge_progress(self, frame) -> bool:
        """Check if challenge is progressing or completed."""
        try:
            # Look for success indicators
            success_selectors = [
                "#success",
                ".success",
                "text=Success",
                "[data-testid='success']",
                ".cf-turnstile-success",
                ".check-mark",
                "svg[class*='success']"
            ]
            
            for selector in success_selectors:
                try:
                    if frame.locator(selector).count() > 0 and frame.locator(selector).is_visible():
                        return True
                except:
                    continue
            
            # Check for any visual changes that indicate progress
            try:
                # Look for any checked checkboxes
                checked_boxes = frame.locator("input[type='checkbox']:checked").count()
                if checked_boxes > 0:
                    return True
                
                # Look for loading or processing indicators
                loading_indicators = frame.locator(".loading, .processing, .spinner").count()
                if loading_indicators > 0:
                    return True
                    
            except:
                pass
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Challenge progress check failed: {str(e)}")
            return False
    
    def handle_cloudflare_challenge(self, page: Page) -> None:
        """Handle Cloudflare challenge with advanced human-like behavior."""
        try:
            self.logger.info("🔍 Checking for Cloudflare challenge")
            
            # Wait for potential challenge to appear
            self.humanized_wait(3.0, 5.0)
            self.take_step_screenshot(page, "check_cloudflare_challenge")
            
            # Check for Cloudflare iframe challenge first
            iframe_selectors = [
                "iframe[title='Widget containing a Cloudflare security challenge']",
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='cloudflare']",
                "iframe[src*='turnstile']"
            ]
            
            for iframe_selector in iframe_selectors:
                try:
                    iframe = page.locator(iframe_selector)
                    if iframe.count() > 0 and iframe.is_visible():
                        self.logger.info("🛡️ Cloudflare iframe challenge detected")
                        self.take_step_screenshot(page, "cloudflare_iframe_detected")
                        
                        # Wait for iframe to fully load
                        self.humanized_wait(2.0, 4.0)
                        
                        # Switch to iframe
                        iframe_element = iframe.first
                        frame = iframe_element.content_frame()
                        
                        if frame:
                            self.logger.info("🔄 Switching to Cloudflare challenge iframe")
                            
                            # Wait for iframe content to load completely
                            self.humanized_wait(3.0, 5.0)
                            
                            # Debug: Take screenshot of iframe content
                            try:
                                self.take_step_screenshot(page, "iframe_content_debug")
                                
                                # Get iframe HTML for debugging
                                iframe_html = frame.evaluate("document.documentElement.outerHTML")
                                self.logger.info(f"📋 Iframe HTML content (first 500 chars): {iframe_html[:500]}")
                                
                            except Exception as e:
                                self.logger.debug(f"Debug info failed: {str(e)}")
                            
                            # Look for the checkbox with multiple strategies
                            checkbox_selectors = [
                                "//label[contains(@class, 'cb-lb')]/input[@type='checkbox']",
                                "//label[contains(@class, 'cb-lb')]",
                                "input[type='checkbox']",
                                "label input[type='checkbox']",
                                ".cb-lb input",
                                ".cf-turnstile-wrapper input",
                                "[data-testid='turnstile-checkbox']",
                                "text=Verify you are human",
                                "//span[text()='Verify you are human']",
                                "*"  # Last resort - find all elements
                            ]
                            
                            # First, let's see what elements exist in the iframe
                            try:
                                all_elements = frame.locator("*").all()
                                self.logger.info(f"🔍 Found {len(all_elements)} total elements in iframe")
                                
                                # Check for any clickable elements
                                clickable_elements = frame.locator("input, button, label, span, div").all()
                                self.logger.info(f"🔍 Found {len(clickable_elements)} potentially clickable elements")
                                
                                for i, element in enumerate(clickable_elements[:10]):  # Check first 10
                                    try:
                                        tag_name = element.evaluate("el => el.tagName")
                                        class_name = element.evaluate("el => el.className")
                                        inner_text = element.evaluate("el => el.innerText")
                                        self.logger.info(f"📝 Element {i}: {tag_name} class='{class_name}' text='{inner_text[:50]}'")
                                    except:
                                        pass
                                        
                            except Exception as e:
                                self.logger.debug(f"Element enumeration failed: {str(e)}")
                            
                            checkbox_clicked = False
                            found_element = None
                            
                            for checkbox_selector in checkbox_selectors:
                                try:
                                    self.logger.info(f"🔍 Trying selector: {checkbox_selector}")
                                    
                                    # Try to find the checkbox
                                    if checkbox_selector == "*":
                                        # Special case - try to click anything that looks like a checkbox area
                                        elements = frame.locator("label, input, div, span").all()
                                        for element in elements:
                                            try:
                                                text = element.evaluate("el => el.innerText || el.textContent || ''")
                                                class_name = element.evaluate("el => el.className || ''")
                                                if any(keyword in text.lower() for keyword in ["verify", "human", "not a robot"]) or \
                                                   any(keyword in class_name.lower() for keyword in ["cb-", "checkbox", "turnstile"]):
                                                    found_element = element
                                                    self.logger.info(f"✅ Found potential checkbox element by content: {text[:50]} class: {class_name}")
                                                    break
                                            except:
                                                continue
                                    else:
                                        checkbox = frame.locator(checkbox_selector)
                                        if checkbox.count() > 0:
                                            found_element = checkbox.first
                                            self.logger.info(f"✅ Found element with selector: {checkbox_selector}")
                                    
                                    if found_element:
                                        try:
                                            # Wait for element to be ready
                                            found_element.wait_for(state="visible", timeout=3000)
                                            
                                            if found_element.is_visible():
                                                self.logger.info(f"✅ Element is visible, attempting interaction")
                                                self.take_step_screenshot(page, f"checkbox_found_{checkbox_selector.replace('/', '_').replace('*', 'wildcard')}")
                                                
                                                # Try multiple click approaches
                                                click_methods = [
                                                    ("hover_focus_click", lambda: self._try_hover_focus_click(found_element)),
                                                    ("force_click", lambda: found_element.click(force=True)),
                                                    ("js_click", lambda: found_element.evaluate("el => el.click()")),
                                                    ("dispatch_event", lambda: found_element.evaluate("""
                                                        el => {
                                                            el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                                                            el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                                                            el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                                                        }
                                                    """)),
                                                    ("coordinate_click", lambda: self._try_coordinate_click(frame, found_element))
                                                ]
                                                
                                                for method_name, method_func in click_methods:
                                                    try:
                                                        self.logger.info(f"🖱️ Trying click method: {method_name}")
                                                        method_func()
                                                        self.humanized_wait(1.0, 2.0)
                                                        self.take_step_screenshot(page, f"after_{method_name}")
                                                        
                                                        # Check if click was successful by looking for changes
                                                        if self._check_challenge_progress(frame):
                                                            self.logger.info(f"✅ Click successful with method: {method_name}")
                                                            checkbox_clicked = True
                                                            break
                                                            
                                                    except Exception as e:
                                                        self.logger.debug(f"Click method {method_name} failed: {str(e)}")
                                                        continue
                                                
                                                if checkbox_clicked:
                                                    break
                                                    
                                        except Exception as e:
                                            self.logger.debug(f"Element interaction failed: {str(e)}")
                                            continue
                                            
                                except Exception as e:
                                    self.logger.debug(f"Selector {checkbox_selector} failed: {str(e)}")
                                    continue
                            
                            if not checkbox_clicked:
                                self.logger.warning("⚠️ Could not find or click Cloudflare checkbox - trying generic iframe click")
                                # Last resort - click center of iframe
                                try:
                                    iframe_bbox = iframe_element.bounding_box()
                                    if iframe_bbox:
                                        center_x = iframe_bbox['x'] + iframe_bbox['width'] / 2
                                        center_y = iframe_bbox['y'] + iframe_bbox['height'] / 2
                                        page.mouse.click(center_x, center_y)
                                        self.logger.info("🖱️ Clicked center of iframe as fallback")
                                        checkbox_clicked = True
                                except Exception as e:
                                    self.logger.error(f"Fallback iframe click failed: {str(e)}")
                            
                            if checkbox_clicked:
                                # Wait for challenge processing
                                self.logger.info("⏳ Waiting for Cloudflare challenge to process...")
                                self.humanized_wait(3.0, 5.0)
                                
                                # Look for success indicators
                                success_selectors = [
                                    "#success",
                                    ".success",
                                    "text=Success",
                                    "[data-testid='success']",
                                    ".cf-turnstile-success"
                                ]
                                
                                challenge_resolved = False
                                
                                # Check for success indicators
                                for success_selector in success_selectors:
                                    try:
                                        success_element = frame.locator(success_selector)
                                        if success_element.count() > 0 and success_element.is_visible():
                                            self.logger.info(f"✅ Challenge success indicator found: {success_selector}")
                                            challenge_resolved = True
                                            break
                                    except:
                                        continue
                                
                                # If no success indicator, check if iframe disappeared
                                if not challenge_resolved:
                                    for _ in range(30):  # Check for 30 seconds
                                        if not page.locator(iframe_selector).is_visible():
                                            self.logger.info("✅ Cloudflare challenge resolved - iframe disappeared")
                                            challenge_resolved = True
                                            break
                                        self.humanized_wait(1.0, 1.0)
                                
                                if challenge_resolved:
                                    self.take_step_screenshot(page, "cloudflare_challenge_resolved")
                                    self.logger.info("✅ Cloudflare challenge completed successfully")
                                    return
                                else:
                                    self.logger.warning("⚠️ Challenge may still be processing")
                                    self.take_step_screenshot(page, "cloudflare_challenge_processing")
                                    return
                            else:
                                self.logger.warning("⚠️ Could not find Cloudflare checkbox in iframe")
                        else:
                            self.logger.warning("⚠️ Could not access iframe content")
                except Exception as e:
                    self.logger.debug(f"Iframe selector {iframe_selector} failed: {str(e)}")
                    continue
            
            # Check for other common Cloudflare challenge indicators
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
    
    
    def perform_automatic_login(self, page: Page, username: str, password: str) -> None:
        """Perform fully automated login with human-like behavior."""
        try:
            self.logger.info("🔐 Starting automated login process")
            self.take_step_screenshot(page, "before_login")
            
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
            
            # Get email input position for human-like interaction
            email_bbox = email_input.bounding_box()
            if email_bbox:
                import random
                email_x = email_bbox['x'] + email_bbox['width'] / 2 + random.uniform(-10, 10)
                email_y = email_bbox['y'] + email_bbox['height'] / 2 + random.uniform(-2, 2)
                self.simulate_human_mouse_movement(page, email_x, email_y)
            
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
            
            # Get password input position for human-like interaction
            password_bbox = password_input.bounding_box()
            if password_bbox:
                import random
                password_x = password_bbox['x'] + password_bbox['width'] / 2 + random.uniform(-10, 10)
                password_y = password_bbox['y'] + password_bbox['height'] / 2 + random.uniform(-2, 2)
                self.simulate_human_mouse_movement(page, password_x, password_y)
            
            password_input.click()
            self.humanized_wait(0.5, 1.0)
            password_input.fill(password)
            self.take_step_screenshot(page, "credentials_filled")
            self.humanized_wait(1.0, 2.0)
            
            # Handle any verification challenges before submitting
            self.logger.info("🔍 Checking for verification challenges before login")
            self.handle_cloudflare_challenge(page)
            
            # Find and click submit button
            submit_button = None
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log in"):not(:has-text("Google")):not(:has-text("Apple"))',
                'button:has-text("Sign in"):not(:has-text("Google")):not(:has-text("Apple"))',
                'button:has-text("Continue"):not(:has-text("Google")):not(:has-text("Apple"))',
                'form button:not(:has-text("Google")):not(:has-text("Apple"))',
                '[role="button"]:not(:has-text("Google")):not(:has-text("Apple"))'
            ]
            
            for selector in submit_selectors:
                try:
                    locator = page.locator(selector)
                    if locator.count() > 0 and locator.first.is_visible() and not locator.first.is_disabled():
                        submit_button = locator.first
                        self.logger.info(f"✅ Found submit button: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                self.logger.error("❌ Could not find enabled submit button")
                self.take_step_screenshot(page, "submit_button_not_found")
                raise Exception("Submit button not found or disabled")
            
            # Human-like submit button interaction
            self.logger.info("🚀 Submitting login form")
            self.take_step_screenshot(page, "before_submit")
            
            # Get submit button position for human-like click
            submit_bbox = submit_button.bounding_box()
            if submit_bbox:
                import random
                submit_x = submit_bbox['x'] + submit_bbox['width'] / 2 + random.uniform(-5, 5)
                submit_y = submit_bbox['y'] + submit_bbox['height'] / 2 + random.uniform(-2, 2)
                self.simulate_human_mouse_movement(page, submit_x, submit_y)
            
            # Humanized submit sequence
            submit_button.hover()
            self.humanized_wait(0.5, 1.0)
            submit_button.focus()
            self.humanized_wait(0.2, 0.5)
            submit_button.click()
            
            self.take_step_screenshot(page, "after_submit_click")
            
            # Wait for login to process
            self.logger.info("⏳ Waiting for login to process...")
            self.humanized_wait(3.0, 5.0)
            
            # Handle any post-login challenges
            self.logger.info("🔍 Checking for post-login challenges")
            self.handle_cloudflare_challenge(page)
            
            # Wait for page to load after login
            page.wait_for_load_state("networkidle", timeout=self.timeout)
            self.humanized_wait(2.0, 4.0)
            
            # Verify login success
            self.logger.info("🔍 Verifying login success...")
            self.take_step_screenshot(page, "login_verification")
            
            # Check for success indicators
            success_selectors = [
                '[data-testid="user-menu-button"]',
                '[data-testid="user-dropdown"]',
                '.user-menu',
                '.account-menu',
                'button[aria-label*="account"]',
                'button[aria-label*="user"]',
                'div[data-testid*="user"]',
                'nav[data-testid*="user"]',
                '[data-testid="dashboard"]',
                '.dashboard',
                'main[role="main"]',
                '[data-testid="zone-list"]'
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
            
            if login_success:
                self.logger.info(f"✅ Automated login successful! (indicator: {found_indicator or 'URL pattern'})")
                self.take_step_screenshot(page, "login_success")
            else:
                self.logger.error(f"❌ Automated login failed - Current URL: {current_url}")
                self.take_step_screenshot(page, "login_failed")
                raise Exception(f"Login failed - still on login page: {current_url}")
            
        except Exception as e:
            self.logger.error(f"❌ Automated login failed: {str(e)}")
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
                    self.logger.info("🔐 Login required - starting automated authentication process")
                    
                    # Handle Cloudflare challenge
                    self.handle_cloudflare_challenge(page)
                    
                    # Step 3: Perform automated login
                    if self.username and self.password:
                        self.logger.info("🤖 Starting fully automated login")
                        self.perform_automatic_login(page, self.username, self.password)
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