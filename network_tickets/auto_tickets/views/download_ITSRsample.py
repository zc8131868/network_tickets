
from django.http import HttpResponse
import os
from django.conf import settings

def download_ITSRsample(request):
    try:
        filename = "ITSR_Network_Ticket_Sample.xlsx"
        print(f"1. Function called with filename: {filename}")
        
        # Construct the file path
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        print(f"2. File path constructed: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"3. File does not exist")
            return HttpResponse(f"File {filename} not found at {file_path}", status=404)
        
        print(f"3. File exists, proceeding to open")
        
        # Read file content into memory
        with open(file_path, 'rb') as f:
            file_content = f.read()
            print(f"4. File read successfully, size: {len(file_content)} bytes")
        
        # Create response with the file content
        response = HttpResponse(file_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        print(f"5. Response created, returning")
        return response
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f"Error: {str(e)}", status=500)

