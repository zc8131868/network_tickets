from django.http import HttpResponse
import os
from django.conf import settings
from pathlib import Path

def download_vpn_network_sample(request):
    try:
        filename = "VPN_Network_Ticket_Sample.xlsx"
        
        # Construct the file path - file is in media directory
        file_path = Path(settings.MEDIA_ROOT) / filename
        
        # Check if file exists
        if not file_path.exists():
            return HttpResponse(f"File {filename} not found at {file_path}", status=404)
        
        # Read file content into memory
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Create response with the file content
        response = HttpResponse(file_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f"Error: {str(e)}", status=500)

