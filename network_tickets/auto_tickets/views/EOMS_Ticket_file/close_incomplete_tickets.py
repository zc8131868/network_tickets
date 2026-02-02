"""
Scheduled task to close incomplete EOMS tickets.

This script is designed to run as a cron job at 6 PM Hong Kong time daily.
It queries the database for tickets with status 'incomplete', attempts to close them,
and updates their status to 'complete' upon success.

Cron setup (6 PM HKT = 10:00 UTC):
    0 10 * * * cd /it_network/network_tickets && /it_network/network_tickets/.venv/bin/python -c "from auto_tickets.views.EOMS_Ticket_file.close_incomplete_tickets import run_close_tickets; run_close_tickets()" >> /var/log/eoms_close_tickets.log 2>&1
"""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_django():
    """Setup Django environment for standalone script execution."""
    import os
    import sys
    import django
    
    # Add the project root to the path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.insert(0, project_root)
    
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
    
    # Setup Django
    django.setup()


async def close_incomplete_tickets():
    """
    Main function to close all incomplete tickets.
    
    - Queries EOMS_Tickets for entries with ticket_status='incomplete'
    - Calls close_ticket() for each ticket
    - Updates ticket_status to 'complete' on success
    """
    from auto_tickets.models import EOMS_Tickets
    from auto_tickets.views.ITSR_Tools.eoms_complete_ticket import close_ticket
    from asgiref.sync import sync_to_async
    
    hk_tz = ZoneInfo('Asia/Hong_Kong')
    current_time = datetime.now(hk_tz)
    
    logger.info(f"{'='*60}")
    logger.info(f"Starting scheduled ticket closing task")
    logger.info(f"Current time (HKT): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}")
    
    # Get all incomplete tickets
    @sync_to_async
    def get_incomplete_tickets():
        return list(EOMS_Tickets.objects.filter(ticket_status='incomplete'))
    
    @sync_to_async
    def update_ticket_status(ticket):
        ticket.ticket_status = 'complete'
        ticket.save()
    
    incomplete_tickets = await get_incomplete_tickets()
    
    if not incomplete_tickets:
        logger.info("No incomplete tickets found. Nothing to process.")
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "results": []
        }
    
    logger.info(f"Found {len(incomplete_tickets)} incomplete ticket(s) to process")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for ticket in incomplete_tickets:
        inst_id = ticket.eoms_ticket_number
        logger.info(f"\n{'─'*40}")
        logger.info(f"Processing ticket: {inst_id}")
        logger.info(f"Department: {ticket.department}")
        logger.info(f"Requestor: {ticket.requestor}")
        logger.info(f"Created: {ticket.create_datetime}")
        
        try:
            # Call close_ticket function
            result = await close_ticket(inst_id=inst_id, opinion="同意", headless=True)
            
            if result.get('success'):
                logger.info(f"✅ Successfully closed ticket: {inst_id}")
                
                # Update ticket status in database
                await update_ticket_status(ticket)
                logger.info(f"✅ Updated ticket status to 'complete' in database")
                
                success_count += 1
                results.append({
                    "inst_id": inst_id,
                    "success": True,
                    "message": result.get('message', 'Ticket closed successfully')
                })
            else:
                error_msg = result.get('message') or result.get('error', 'Unknown error')
                logger.warning(f"❌ Failed to close ticket {inst_id}: {error_msg}")
                failed_count += 1
                results.append({
                    "inst_id": inst_id,
                    "success": False,
                    "message": error_msg
                })
                
        except Exception as e:
            logger.error(f"❌ Exception while closing ticket {inst_id}: {str(e)}")
            failed_count += 1
            results.append({
                "inst_id": inst_id,
                "success": False,
                "message": str(e)
            })
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Ticket closing task completed")
    logger.info(f"Total processed: {len(incomplete_tickets)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"{'='*60}")
    
    return {
        "total": len(incomplete_tickets),
        "success": success_count,
        "failed": failed_count,
        "results": results
    }


def run_close_tickets():
    """
    Entry point for running the ticket closing task.
    Sets up Django and runs the async function.
    """
    setup_django()
    return asyncio.run(close_incomplete_tickets())


if __name__ == "__main__":
    # When run directly, setup Django and execute
    setup_django()
    result = asyncio.run(close_incomplete_tickets())
    print(f"\nFinal Result: {result}")
