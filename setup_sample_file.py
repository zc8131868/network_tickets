#!/usr/bin/env python
"""
Script to set up the sample.xlsx file for download functionality.
Run this script to create a DownloadFile entry in the database.
"""

import os
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'network_tickets.settings')
django.setup()

from auto_tickets.models import DownloadFile

def setup_sample_file():
    """Create a DownloadFile entry for the sample.xlsx file"""
    
    # Check if sample file already exists
    try:
        existing_file = DownloadFile.objects.get(title='Sample')
        print(f"Sample file already exists: {existing_file.file}")
        return existing_file
    except DownloadFile.DoesNotExist:
        pass
    
    # Look for existing sample files
    sample_files = [
        'auto_tickets/ITSR_sample.xlsx',
        'auto_tickets/sample.xlsx',
        'sample.xlsx'
    ]
    
    sample_file_path = None
    for file_path in sample_files:
        full_path = os.path.join(os.getcwd(), file_path)
        if os.path.exists(full_path):
            sample_file_path = full_path
            break
    
    if not sample_file_path:
        print("No sample.xlsx file found. Please create one and place it in the auto_tickets directory.")
        print("You can also upload it through the Django admin interface.")
        return None
    
    # Create DownloadFile entry
    try:
        from django.core.files import File
        with open(sample_file_path, 'rb') as f:
            django_file = File(f, name=os.path.basename(sample_file_path))
            download_file = DownloadFile.objects.create(
                title='Sample',
                file=django_file
            )
            print(f"Successfully created DownloadFile entry: {download_file.file}")
            return download_file
    except Exception as e:
        print(f"Error creating DownloadFile entry: {e}")
        return None

if __name__ == "__main__":
    setup_sample_file()
