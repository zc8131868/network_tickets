from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import sys
import os
import asyncio
import json
from django.contrib.auth.decorators import login_required

# Add the ai_tools directory to the Python path
ai_tools_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ai_tools')
sys.path.insert(0, ai_tools_path)

@login_required
def mercury_chat_view(request):
    """
    Render the Mercury chat interface page
    """
    return render(request, 'mercury_chat.html')


@csrf_exempt
@require_http_methods(["POST"])
def mercury_chat_api(request):
    """
    API endpoint to handle chat queries from the Mercury AI assistant
    Accepts POST requests with JSON data containing the user's question
    Returns JSON response with the AI's answer
    """
    try:
        # Parse the JSON data from request body
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({
                'success': False,
                'error': 'Question cannot be empty'
            }, status=400)
        
        # Run the query asynchronously
        try:
            # Lazy import to avoid loading AI modules on Django startup
            # Ensure the path is in sys.path
            import sys
            import os
            ai_tools_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ai_tools')
            if ai_tools_path not in sys.path:
                sys.path.insert(0, ai_tools_path)
            
            from chromadb_agent import run_query
            answer = asyncio.run(run_query(question))
            
            if answer:
                return JsonResponse({
                    'success': True,
                    'answer': answer,
                    'question': question
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No answer generated. Please try again.'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error processing query: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

