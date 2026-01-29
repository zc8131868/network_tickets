from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.conf import settings
import os
import mimetypes
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@login_required
def serve_itsr_file(request, filename):
    """
    Serve files from the itsr_files directory.
    Security: Only allows files from the itsr_files directory.
    """
    # Sanitize filename to prevent directory traversal
    filename = os.path.basename(filename)

    itsr_files_dir = Path(settings.BASE_DIR) / 'auto_tickets' / 'itsr_files'
    file_path = itsr_files_dir / filename

    # Check if file exists and is within the allowed directory
    if not file_path.exists() or not file_path.is_file():
        logger.warning("ITSR file not found: %s", file_path)
        raise Http404("File not found")

    # Verify the file is actually in the itsr_files directory (security check)
    try:
        real_file_path = file_path.resolve(strict=True)
    except FileNotFoundError:
        logger.warning("ITSR file resolve failed: %s", file_path)
        raise Http404("File not found")

    real_itsr_files_dir = itsr_files_dir.resolve()
    if not str(real_file_path).startswith(str(real_itsr_files_dir)):
        logger.warning("Invalid ITSR file path: %s", real_file_path)
        raise Http404("Invalid file path")

    try:
        content_type, _ = mimetypes.guess_type(str(real_file_path))
        response = FileResponse(
            open(real_file_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type=content_type or 'application/octet-stream',
        )
        return response
    except Exception as e:
        logger.exception("Error serving ITSR file: %s", real_file_path)
        raise Http404(f"Error serving file: {str(e)}")
