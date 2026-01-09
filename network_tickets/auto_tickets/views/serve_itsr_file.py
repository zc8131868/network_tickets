from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
import os
from django.conf import settings


@login_required
def serve_itsr_file(request, filename):
    """
    Serve files from the itsr_files directory.
    Security: Only allows files from the itsr_files directory.
    """
    # Sanitize filename to prevent directory traversal
    filename = os.path.basename(filename)
    
    # Construct file path
    file_path = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files', filename)
    
    # Check if file exists and is within the allowed directory
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    # Verify the file is actually in the itsr_files directory (security check)
    itsr_files_dir = os.path.join(settings.BASE_DIR, 'auto_tickets', 'itsr_files')
    real_file_path = os.path.realpath(file_path)
    real_itsr_files_dir = os.path.realpath(itsr_files_dir)
    
    if not real_file_path.startswith(real_itsr_files_dir):
        raise Http404("Invalid file path")
    
    try:
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        raise Http404(f"Error serving file: {str(e)}")
