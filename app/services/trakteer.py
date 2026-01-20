import requests
import re
import json
from flask import current_app
from urllib.parse import unquote

class TrakteerService:
    def __init__(self):
        self.creator_username = current_app.config.get('TRAKTEER_CREATOR_USERNAME')
        self.creator_id = current_app.config.get('TRAKTEER_CREATOR_ID')
        self.unit_id = current_app.config.get('TRAKTEER_UNIT_ID')
        
        price = current_app.config.get('TRAKTEER_UNIT_PRICE')
        self.unit_price = int(price) if price else 5000
        
        self.webhook_token = current_app.config.get('TRAKTEER_WEBHOOK_TOKEN')
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    def get_qris(self, order_id, total_amount, email):
        """
        Generate QRIS string for a given order.
        """
        if not all([self.creator_username, self.creator_id, self.unit_id, self.unit_price]):
            raise ValueError("Trakteer configuration missing")

        # Calculate quantity
        quantity = -(-total_amount // self.unit_price) # Ceiling division
        if quantity < 1:
            quantity = 1

        # Use first 8 chars of ID for shorter identifiers
        # order_id might be int, convert to str
        short_order_id = str(order_id)[:8]

        # Unique Email Construction
        if '@' in email:
            user, domain = email.split('@')
            target_email = f"{user}+{short_order_id}@{domain}"
        else:
            target_email = email

        target_url = f"https://trakteer.id/{self.creator_username}"
        api_url = "https://api.trakteer.id/v2/fe/pay/xendit/qris"

        session = requests.Session()
        session.headers.update({'User-Agent': self.user_agent})

        # 1. Pre-flight GET to get cookies and XSRF token
        try:
            resp = session.get(target_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to connect to Trakteer: {str(e)}")

        # Extract raw cookies
        raw_cookies = resp.raw.headers.getlist('Set-Cookie')
        
        cookie_parts = []
        xsrf_token = None
        
        for cookie_str in raw_cookies:
            first_part = cookie_str.split(';')[0]
            cookie_parts.append(first_part)
            
            if first_part.startswith('XSRF-TOKEN='):
                value = first_part.split('=', 1)[1]
                xsrf_token = unquote(value)

        if not xsrf_token:
            # Fallback to session cookies
            xsrf_token = session.cookies.get('XSRF-TOKEN')
            if xsrf_token:
                xsrf_token = unquote(xsrf_token)
            else:
                 raise Exception("Failed to get XSRF-TOKEN from Trakteer")
        
        cookie_string = "; ".join(cookie_parts)

        display_name = f"Order #{short_order_id}"
        
        # PRIORITIZE REF CODE: Ensure it's at the start to avoid truncation
        ref_code = f"[Ref:{order_id}]"
        support_msg = f"{ref_code} Order #{short_order_id}"

        payload = {
            "form": "create-tip",
            "creator_id": self.creator_id,
            "unit_id": self.unit_id,
            "quantity": quantity,
            "display_name": display_name,
            "support_message": support_msg,
            "times": "once",
            "payment_method": "qris",
            "is_showing_email": "on",
            "is_remember_next": "on",
            "guest_email": target_email
        }

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-XSRF-TOKEN': xsrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://teer.id',
            'Referer': 'https://teer.id/',
            'Cookie': cookie_string
        }

        try:
            post_resp = session.post(api_url, json=payload, headers=headers)
            post_resp.raise_for_status()
            json_api = post_resp.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"Trakteer API Error: {str(e)}"
            if e.response is not None:
                try:
                    error_msg += f" Response: {e.response.text}"
                except:
                    pass
            raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Trakteer API Error: {str(e)}")

        # 3. Extract Checkout URL
        checkout_url = None
        if 'result' in json_api and 'checkout_url' in json_api['result']:
            checkout_url = json_api['result']['checkout_url']
        elif 'checkout_url' in json_api:
            checkout_url = json_api['checkout_url']
        elif 'response_trakteer' in json_api and 'checkout_url' in json_api['response_trakteer']:
            checkout_url = json_api['response_trakteer']['checkout_url']

        if not checkout_url:
            raise Exception(f"Failed to get checkout URL. Response: {json_api}")

        # 4. Visit Checkout URL to get QRIS string
        try:
            checkout_resp = session.get(checkout_url)
            checkout_resp.raise_for_status()
            html_content = checkout_resp.text
        except Exception as e:
            raise Exception(f"Failed to load checkout page: {str(e)}")

        # 5. Regex extraction
        match = re.search(r'(000201[^"\'<\\\\]+)', html_content)
        if match:
            qris_string = match.group(1)
            return unquote(qris_string)
        else:
            raise Exception("Failed to extract QRIS string from checkout page")

    def verify_webhook(self, received_token):
        return self.webhook_token and received_token == self.webhook_token

    def parse_webhook_message(self, message):
        """
        Extract Order ID from the supporter message.
        """
        match = re.search(r'\[Ref:([a-zA-Z0-9\-]+)\]', message)
        if match:
            return match.group(1)
        return None
