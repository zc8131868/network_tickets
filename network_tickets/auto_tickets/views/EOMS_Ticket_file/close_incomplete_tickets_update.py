"""
Scheduled task to close incomplete EOMS tickets.

This script replaces close_incomplete_tickets.py with an improved approach:
- Uses EOmsCompleteClient which calls pendingJson + taskDetail + complete APIs
  (instead of the broken taskApprove API)
- Logs in once and fetches pending tasks once for efficient batch processing
- Only closes tickets found in both DB (incomplete) and EOMS (pending)
- Leaves tickets alone if not found in EOMS pending tasks

Cron setup (6 PM HKT = 10:00 UTC):
    0 10 * * * cd /it_network/network_tickets && /it_network/network_tickets/.venv/bin/python -c "from auto_tickets.views.EOMS_Ticket_file.close_incomplete_tickets_update import run_close_tickets; run_close_tickets()" >> /var/log/eoms_close_tickets.log 2>&1
"""

import json
import asyncio
import os
import logging
from datetime import datetime
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo

import requests
import urllib3
from playwright.async_api import async_playwright, Page

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================
# EOMS Configuration
# ============================================================
DEFAULT_CONFIG = {
    "username": "p7869",
    "password": "Ericsson_5",
}


class EOmsCompleteClient:
    """EOMS ticket-closing client.

    Authenticates via Playwright (headless Chromium), then uses REST APIs
    to list pending tasks and complete/close them.
    """

    STORAGE_STATE_FILE = "eoms_complete_auth_state.json"

    def __init__(self, username: str = None, password: str = None, storage_state_path: str = None):
        self.base_url = "https://eoms2.cmhktry.com/x5"
        self.cookies = {}
        self.headers = {}
        self.username = username or DEFAULT_CONFIG["username"]
        self.password = password or DEFAULT_CONFIG["password"]
        self.storage_state_path = storage_state_path or self.STORAGE_STATE_FILE

    # ----------------------------------------------------------
    # Authentication
    # ----------------------------------------------------------
    async def login(self, headless: bool = True, use_cache: bool = True) -> bool:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)

            storage_state = None
            if use_cache and os.path.exists(self.storage_state_path):
                logger.info(f"Found cached auth state: {self.storage_state_path}")
                storage_state = self.storage_state_path

            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 800},
                storage_state=storage_state,
            )
            page = await context.new_page()

            captured_headers = {}

            async def capture_request(request):
                if "eoms2.cmhktry.com" in request.url:
                    captured_headers.update(request.headers)

            page.on("request", capture_request)

            logger.info(f"Opening: {self.base_url}")
            await page.goto(self.base_url, wait_until="networkidle")
            await asyncio.sleep(2)

            current_url = page.url
            need_login = "ncas.cmhktry.com" in current_url or "cas" in current_url.lower()

            if need_login:
                if storage_state:
                    logger.info("Cached auth state expired, re-authenticating")
                logger.info("Auto-login in progress...")
                try:
                    await self._auto_login(page, timeout_seconds=30)
                    logger.info("Login successful")
                except Exception as e:
                    logger.error(f"Login failed: {e}")
                    await browser.close()
                    return False
            else:
                logger.info("Using cached auth state")

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            cookies_list = await context.cookies()
            self.cookies = {c["name"]: c["value"] for c in cookies_list}
            self.headers = captured_headers

            logger.info(f"Captured {len(self.cookies)} cookies")

            await context.storage_state(path=self.storage_state_path)
            logger.info("Auth state cached")

            await browser.close()
            return True

    async def _auto_login(self, page: Page, timeout_seconds: int = 30):
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)

        username_selectors = [
            'input#username', 'input[name="username"]',
            'input[type="text"]:first-of-type',
        ]
        username_input = None
        for selector in username_selectors:
            try:
                username_input = await page.wait_for_selector(selector, timeout=3000)
                if username_input:
                    break
            except Exception:
                continue
        if not username_input:
            raise Exception("Username input not found")

        password_selectors = [
            'input#password', 'input[name="password"]',
            'input[type="password"]',
        ]
        password_input = None
        for selector in password_selectors:
            try:
                password_input = await page.wait_for_selector(selector, timeout=3000)
                if password_input:
                    break
            except Exception:
                continue
        if not password_input:
            raise Exception("Password input not found")

        await username_input.fill("")
        await username_input.type(self.username, delay=50)
        await password_input.fill("")
        await password_input.type(self.password, delay=50)
        await asyncio.sleep(0.5)

        submit_selectors = [
            'button[type="submit"]', 'input[type="submit"]',
            'button:has-text("登录")', 'button:has-text("Login")',
        ]
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = await page.wait_for_selector(selector, timeout=2000)
                if submit_button:
                    break
            except Exception:
                continue

        if submit_button:
            await submit_button.click()
        else:
            await password_input.press("Enter")

        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError("Login timed out")
            if "eoms2.cmhktry.com" in page.url:
                if "/login" not in page.url.lower() and "cas" not in page.url.lower():
                    await page.wait_for_load_state("networkidle")
                    return
            await asyncio.sleep(0.5)

    # ----------------------------------------------------------
    # API helpers
    # ----------------------------------------------------------
    def _make_session(self) -> requests.Session:
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        return session

    def _api_headers(self, content_type: str = None) -> dict:
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }
        if content_type:
            headers["Content-Type"] = content_type
            headers["Accept"] = "*/*"
            headers["Origin"] = "https://eoms2.cmhktry.com"
        return headers

    # ----------------------------------------------------------
    # Pending tasks
    # ----------------------------------------------------------
    def get_my_pending_tasks(self) -> list:
        """GET /x5/office/receivedProcess/pendingJson — returns rows of pending tasks.

        Each row contains:
          id / taskId  — task ID (used for taskDetail & complete)
          procInstId   — process instance ID (matches eoms_ticket_number in DB)
          procDefKey   — e.g. "ServiceConfigurationTicket"
        """
        url = f"{self.base_url}/office/receivedProcess/pendingJson"
        session = self._make_session()

        try:
            response = session.get(url, headers=self._api_headers(), verify=False)
            if response.status_code != 200:
                logger.error(f"pendingJson failed: HTTP {response.status_code}")
                return []
            data = response.json()
            rows = data.get("rows", [])
            logger.info(f"Fetched {data.get('total', 0)} pending task(s) from EOMS")
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch pending tasks: {e}")
            return []

    def get_task_detail(self, task_id: str) -> dict:
        """GET /x5/flow/task/taskDetail?taskId={taskId}"""
        url = f"{self.base_url}/flow/task/taskDetail"
        session = self._make_session()

        try:
            response = session.get(url, params={"taskId": task_id},
                                   headers=self._api_headers(), verify=False)
            if response.status_code == 200:
                data = response.json()
                task_data = data.get("data", {})
                return {
                    "success": data.get("result", False),
                    "instId": task_data.get("instId", ""),
                    "ServiceConfig": task_data.get("ServiceConfig", {}),
                    "raw": data,
                }
            logger.warning(f"taskDetail HTTP {response.status_code}: {response.text[:200]}")
            return {"success": False}
        except Exception as e:
            logger.error(f"taskDetail failed: {e}")
            return {"success": False}

    def complete_task(
        self,
        task_id: str,
        inst_id: str,
        service_config: dict,
        bpm_form_id: str = "ServiceConfigurationTicket",
        action_name: str = "agree",
        opinion: str = "同意",
    ) -> dict:
        """POST /x5/flow/task/complete"""
        url = f"{self.base_url}/flow/task/complete"
        headers = self._api_headers(content_type="application/x-www-form-urlencoded; charset=UTF-8")

        data_content = {"instId": inst_id, "ServiceConfig": service_config}
        form_data = {
            "taskId": task_id,
            "actionName": action_name,
            "opinion": opinion,
            "bpmFormId": bpm_form_id,
            "data": json.dumps(data_content, ensure_ascii=False),
            "nodeUsers": json.dumps([{"executors": []}]),
        }

        session = self._make_session()
        try:
            response = session.post(url, data=form_data, headers=headers, verify=False)
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"complete_task failed: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------
    # High-level close methods
    # ----------------------------------------------------------
    def close_ticket_by_task_id(self, task_id: str, opinion: str = "同意") -> dict:
        """Close a ticket given its taskId (from pendingJson)."""
        task_detail = self.get_task_detail(task_id)
        if not task_detail.get("success"):
            return {
                "success": False, "instId": None, "taskId": task_id,
                "message": "Failed to get task detail",
            }

        inst_id = task_detail.get("instId")
        service_config = task_detail.get("ServiceConfig", {})

        result = self.complete_task(
            task_id=task_id,
            inst_id=inst_id,
            service_config=service_config,
            opinion=opinion,
        )
        success = result.get("result") == 1
        return {
            "success": success,
            "instId": inst_id,
            "taskId": task_id,
            "message": result.get("message", "unknown"),
            "response": result,
        }


# ============================================================
# Django integration
# ============================================================
def setup_django():
    """Bootstrap Django ORM for standalone script execution."""
    import sys
    import django

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
    django.setup()


async def close_incomplete_tickets():
    """Query DB for incomplete tickets, match against EOMS pending tasks, and close them.

    Flow:
    1. Login to EOMS once
    2. Fetch all pending tasks from EOMS once (build procInstId -> taskId map)
    3. Query DB for tickets with ticket_status='incomplete'
    4. For each incomplete ticket whose eoms_ticket_number appears in the pending
       tasks map, close it via taskDetail + complete APIs
    5. On success, update ticket_status to 'complete' in DB
    6. If not found in EOMS pending tasks, leave as 'incomplete'
    """
    from auto_tickets.models import EOMS_Tickets
    from asgiref.sync import sync_to_async

    hk_tz = ZoneInfo('Asia/Hong_Kong')
    current_time = datetime.now(hk_tz)

    logger.info("=" * 60)
    logger.info("Starting scheduled ticket closing task")
    logger.info(f"Current time (HKT): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # --- Step 1: Login to EOMS ---
    client = EOmsCompleteClient()
    login_ok = await client.login(headless=True)
    if not login_ok:
        logger.error("EOMS login failed — aborting")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "results": []}

    # --- Step 2: Fetch pending tasks and build lookup ---
    pending_tasks = client.get_my_pending_tasks()
    pending_map: dict[str, str] = {}
    for task in pending_tasks:
        proc_inst_id = str(task.get("procInstId", ""))
        task_id = str(task.get("taskId") or task.get("id", ""))
        if proc_inst_id and task_id:
            pending_map[proc_inst_id] = task_id

    logger.info(f"Built pending-task lookup: {len(pending_map)} entry/entries")

    # --- Step 3: Query DB for incomplete tickets ---
    @sync_to_async
    def get_incomplete_tickets():
        return list(EOMS_Tickets.objects.filter(ticket_status='incomplete'))

    @sync_to_async
    def update_ticket_status(ticket):
        ticket.ticket_status = 'complete'
        ticket.save()

    incomplete_tickets = await get_incomplete_tickets()

    if not incomplete_tickets:
        logger.info("No incomplete tickets found in database. Nothing to process.")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "results": []}

    logger.info(f"Found {len(incomplete_tickets)} incomplete ticket(s) in database")

    # --- Step 4: Process each ticket ---
    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for ticket in incomplete_tickets:
        eoms_number = ticket.eoms_ticket_number
        logger.info("-" * 40)
        logger.info(f"Processing ticket: {eoms_number}")
        logger.info(f"  Department: {ticket.department}")
        logger.info(f"  Requestor:  {ticket.requestor}")
        logger.info(f"  Created:    {ticket.create_datetime}")

        task_id = pending_map.get(eoms_number)

        if not task_id:
            logger.info(f"  SKIPPED — ticket {eoms_number} not found in EOMS pending tasks")
            skipped_count += 1
            results.append({
                "eoms_ticket_number": eoms_number,
                "success": False,
                "message": "Not found in EOMS pending tasks (may already be processed)",
            })
            continue

        logger.info(f"  Matched EOMS taskId: {task_id}")

        try:
            result = client.close_ticket_by_task_id(task_id=task_id, opinion="同意")

            if result.get("success"):
                logger.info(f"  Successfully closed ticket {eoms_number} on EOMS")
                await update_ticket_status(ticket)
                logger.info(f"  Updated DB ticket_status to 'complete'")
                success_count += 1
                results.append({
                    "eoms_ticket_number": eoms_number,
                    "success": True,
                    "message": result.get("message", "Ticket closed successfully"),
                })
            else:
                error_msg = result.get("message") or result.get("error", "Unknown error")
                logger.warning(f"  Failed to close ticket {eoms_number}: {error_msg}")
                failed_count += 1
                results.append({
                    "eoms_ticket_number": eoms_number,
                    "success": False,
                    "message": error_msg,
                })
        except Exception as e:
            logger.error(f"  Exception while closing ticket {eoms_number}: {e}")
            failed_count += 1
            results.append({
                "eoms_ticket_number": eoms_number,
                "success": False,
                "message": str(e),
            })

        await asyncio.sleep(1)

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("Ticket closing task completed")
    logger.info(f"  Total incomplete in DB: {len(incomplete_tickets)}")
    logger.info(f"  Successful:            {success_count}")
    logger.info(f"  Failed:                {failed_count}")
    logger.info(f"  Skipped (not pending): {skipped_count}")
    logger.info("=" * 60)

    return {
        "total": len(incomplete_tickets),
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "results": results,
    }


def run_close_tickets():
    """Sync entry point — sets up Django and runs the async closing task."""
    setup_django()
    return asyncio.run(close_incomplete_tickets())


if __name__ == "__main__":
    setup_django()
    result = asyncio.run(close_incomplete_tickets())
    print(f"\nFinal Result: {result}")
