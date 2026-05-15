"""
Minimal Chrome DevTools Protocol (CDP) client.

Connects directly to Chrome's debugging WebSocket without any automation
frameworks (no Selenium, no Playwright). This avoids setting navigator.webdriver
and other automation flags that bet365 detects.
"""

import json
import threading
import time
import websocket


class CDPClient:
    """Direct CDP WebSocket client for Chrome tab communication."""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0
        self._responses = {}
        self._events = []
        self._lock = threading.Lock()
        self._recv_thread = None
        self._running = False

    def connect(self):
        """Connect to Chrome tab via WebSocket."""
        try:
            self.ws = websocket.create_connection(
                self.ws_url,
                timeout=10,
                suppress_origin=True,  # Don't send Origin header
            )
            self._running = True
            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()
            print(f"[CDP] Connected to Chrome tab")
            return True
        except Exception as e:
            print(f"[CDP] Connection failed: {e}")
            return False

    def disconnect(self):
        """Close the WebSocket connection."""
        self._running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        print("[CDP] Disconnected")

    def _receive_loop(self):
        """Background thread that receives all CDP messages."""
        while self._running:
            try:
                if not self.ws:
                    break
                raw = self.ws.recv()
                if not raw:
                    continue
                msg = json.loads(raw)
                with self._lock:
                    if 'id' in msg:
                        # This is a response to a command we sent
                        self._responses[msg['id']] = msg
                    else:
                        # This is an event
                        self._events.append(msg)
                        # Keep only last 1000 events to prevent memory issues
                        if len(self._events) > 1000:
                            self._events = self._events[-500:]
            except websocket.WebSocketTimeoutException:
                continue
            except websocket.WebSocketConnectionClosedException:
                print("[CDP] Connection closed by Chrome")
                self._running = False
                break
            except Exception as e:
                if self._running:
                    # Silently ignore parse errors during shutdown
                    pass

    def send_command(self, method, params=None, timeout=30):
        """Send a CDP command and wait for its response."""
        self._msg_id += 1
        msg_id = self._msg_id

        message = {'id': msg_id, 'method': method}
        if params:
            message['params'] = params

        try:
            self.ws.send(json.dumps(message))
        except Exception as e:
            print(f"[CDP] Send error: {e}")
            return None

        # Wait for response
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if msg_id in self._responses:
                    resp = self._responses.pop(msg_id)
                    if 'error' in resp:
                        err = resp['error']
                        print(f"[CDP] Error: {err.get('message', 'Unknown error')}")
                        return None
                    return resp.get('result', {})
            time.sleep(0.05)

        print(f"[CDP] Timeout waiting for response to {method}")
        return None

    def evaluate(self, expression, timeout=30):
        """Execute JavaScript in the page context and return the result."""
        result = self.send_command('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True,
            'awaitPromise': False,
            'timeout': timeout * 1000,
        }, timeout=timeout)

        if not result:
            return None

        remote_obj = result.get('result', {})
        if remote_obj.get('type') == 'string':
            return remote_obj.get('value')
        elif remote_obj.get('type') == 'object' and remote_obj.get('value'):
            return json.dumps(remote_obj['value'])
        elif remote_obj.get('type') == 'undefined':
            return None
        else:
            # Try to get the value directly
            val = remote_obj.get('value')
            if val is not None:
                return str(val)
            return remote_obj.get('description', str(remote_obj))

    def receive_event(self, timeout=5):
        """Get the next CDP event, or None if timeout."""
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if self._events:
                    return self._events.pop(0)
            time.sleep(0.05)
        return None

    def get_document_html(self, depth=3):
        """Get the page's DOM as HTML."""
        # First get the root node
        result = self.send_command('DOM.getDocument', {'depth': 0})
        if not result:
            return None

        root_id = result.get('root', {}).get('nodeId')
        if not root_id:
            return None

        # Get outer HTML
        html_result = self.send_command('DOM.getOuterHTML', {'nodeId': root_id})
        if html_result:
            return html_result.get('outerHTML', '')
        return None

    def take_screenshot(self, format='png', quality=80):
        """Take a screenshot of the page (returns base64-encoded image)."""
        params = {'format': format}
        if format == 'jpeg':
            params['quality'] = quality
        result = self.send_command('Page.captureScreenshot', params)
        if result:
            return result.get('data')  # base64 encoded
        return None

    def get_page_info(self):
        """Get basic page info (URL, title)."""
        url = self.evaluate('window.location.href')
        title = self.evaluate('document.title')
        return {'url': url, 'title': title}

    def navigate(self, url):
        """Navigate to a URL."""
        return self.send_command('Page.navigate', {'url': url})

    def wait_for_load(self, timeout=30):
        """Wait for the page to finish loading."""
        start = time.time()
        while time.time() - start < timeout:
            state = self.evaluate('document.readyState')
            if state == 'complete':
                return True
            time.sleep(0.5)
        return False
