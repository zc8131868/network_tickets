"""
ITSR ticket attachments stored under auto_tickets/itsr_files/ by ticket number prefix.
"""
import logging
import os
from datetime import datetime

from django.conf import settings

logger = logging.getLogger(__name__)


def get_itsr_files_dir():
    return os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')


def safe_ticket_file_prefix(itsr_ticket_number):
    safe = str(itsr_ticket_number or '').strip().replace('/', '_').replace('\\', '_')
    return safe, (f'{safe}_' if safe else '')


def attachment_paths_for_ticket(itsr_files_dir, itsr_ticket_number):
    """
    Paths to files for this ticket: ``{ticket}_*`` and legacy ``{ticket}.ext``.
    Uses startswith (not glob) so [], *, ? in ticket numbers do not break matching.
    """
    safe, prefix = safe_ticket_file_prefix(itsr_ticket_number)
    if not safe or not os.path.isdir(itsr_files_dir):
        return []
    paths = []
    try:
        for name in os.listdir(itsr_files_dir):
            path = os.path.join(itsr_files_dir, name)
            if not os.path.isfile(path):
                continue
            if prefix and name.startswith(prefix):
                paths.append(path)
                continue
            stem, _ext = os.path.splitext(name)
            if stem == safe:
                paths.append(path)
    except OSError:
        pass
    return paths


def delete_attachments_for_ticket_number(itsr_files_dir, itsr_ticket_number):
    """
    Remove all itsr_files entries for this ticket number.
    Used when the DB row is deleted or before re-creating a ticket with the same number.
    Returns the number of files removed.
    """
    n = 0
    for path in attachment_paths_for_ticket(itsr_files_dir, itsr_ticket_number):
        try:
            os.remove(path)
            n += 1
        except OSError as e:
            logger.warning('Could not remove ITSR attachment %s: %s', path, e)
    return n


def file_entries_for_ticket(itsr_files_dir, ticket):
    """Sorted file metadata for search results / download UI."""
    paths = attachment_paths_for_ticket(itsr_files_dir, ticket.itsr_ticket_number)
    file_list = []
    for file_path in paths:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_mtime = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
        file_list.append({
            'name': file_name,
            'path': file_path,
            'size': file_size,
            'date': file_date,
            'mtime': file_mtime,
            'url_name': file_name,
        })
    return sorted(file_list, key=lambda x: x['mtime'], reverse=True)
