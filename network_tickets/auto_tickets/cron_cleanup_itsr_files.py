#!/usr/bin/env python
"""
Cron script to clean up old ITSR files from the itsr_files directory.
Removes files older than 6 months.

Usage (cron):
    0 2 * * 0 cd /it_network/network_tickets && /it_network/network_tickets/.venv/bin/python auto_tickets/cron_cleanup_itsr_files.py >> /var/log/itsr_files_cleanup.log 2>&1
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()

from django.conf import settings
from auto_tickets.views.ticket_management import cleanup_old_files
from datetime import datetime


def main():
    itsr_files_dir = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting ITSR files cleanup...")
    print(f"Directory: {itsr_files_dir}")
    
    if not os.path.exists(itsr_files_dir):
        print("Directory does not exist. Nothing to clean up.")
        return
    
    # Count files before cleanup
    file_count_before = len([f for f in os.listdir(itsr_files_dir) if os.path.isfile(os.path.join(itsr_files_dir, f))])
    print(f"Files before cleanup: {file_count_before}")
    
    # Run cleanup (2 months retention)
    deleted_count, error_count = cleanup_old_files(itsr_files_dir, retention_months=2)
    
    file_count_after = len([f for f in os.listdir(itsr_files_dir) if os.path.isfile(os.path.join(itsr_files_dir, f))])
    
    print(f"Deleted: {deleted_count}, Errors: {error_count}")
    print(f"Files after cleanup: {file_count_after}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cleanup complete.")


if __name__ == '__main__':
    main()
