"""
ITSR Close API Views
====================
API endpoints for the multi-step ITSR ticket closing workflow.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
import json
import logging

from auto_tickets.views.ITSR_Tools.itsr_close import (
    create_close_session,
    submit_credentials,
    submit_sms_code,
    get_session_status,
    cancel_session,
    wait_close_result
)
from auto_tickets.models import ITSR_Network

logger = logging.getLogger(__name__)

def _build_requestor_map(ticket_numbers):
    """
    Build a mapping {itsr_ticket_number: requestor} for display in close results.
    """
    nums = [n for n in (ticket_numbers or []) if n]
    if not nums:
        return {}
    try:
        return dict(
            ITSR_Network.objects.filter(itsr_ticket_number__in=nums)
            .values_list('itsr_ticket_number', 'requestor')
        )
    except Exception as e:
        logger.warning(f"Failed to build requestor map: {e}")
        return {}


@login_required
@require_http_methods(["POST"])
def create_close_session_api(request):
    """
    Step 1: Create a close session for selected tickets
    
    POST data:
    {
        "ticket_ids": ["1", "2", "3"],  // Django ticket IDs
        "select_all": false,            // Optional: if true, get all tickets from query
        "handler": "ZHENG Cheng",        // Optional: for select_all mode
        "update_db": true               // Optional: update database after closing
    }
    
    Returns:
    {
        "success": true,
        "session_id": "abc12345",
        "ticket_count": 3,
        "ticket_numbers": ["ITSR001", "ITSR002", "ITSR003"]
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
        ticket_ids = data.get('ticket_ids', [])
        select_all = data.get('select_all', False)
        handler = data.get('handler', '')
        update_db = data.get('update_db', True)
        
        # Get ITSR ticket numbers
        itsr_numbers = []
        
        if select_all and handler:
            # Get all tickets matching criteria
            query = ITSR_Network.objects.filter(
                handler=handler,
                ticket_status='complete',
                itsr_status='open'
            )
            itsr_numbers = list(query.values_list('itsr_ticket_number', flat=True))
        elif ticket_ids:
            # Get selected tickets
            for ticket_id in ticket_ids:
                try:
                    ticket = ITSR_Network.objects.get(id=ticket_id)
                    if ticket.itsr_ticket_number and ticket.itsr_status == 'open':
                        itsr_numbers.append(ticket.itsr_ticket_number)
                except ITSR_Network.DoesNotExist:
                    continue
        
        if not itsr_numbers:
            return JsonResponse({
                'success': False,
                'error': 'No valid tickets found to close. Tickets must have itsr_status="open".'
            }, status=400)
        
        # Create close session
        session_id = create_close_session(itsr_numbers, update_db=update_db)
        
        logger.info(f"Created close session {session_id} for {len(itsr_numbers)} tickets")
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'ticket_count': len(itsr_numbers),
            'ticket_numbers': itsr_numbers
        })
        
    except Exception as e:
        logger.error(f"Error creating close session: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def submit_credentials_api(request):
    """
    Step 2: Submit username and password
    
    POST data:
    {
        "session_id": "abc12345",
        "username": "PY0121",
        "password": "password123"
    }
    
    Returns:
    {
        "success": true,
        "message": "Waiting for SMS code"
    }
    or
    {
        "success": false,
        "error": "Login failed: invalid credentials"
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
        session_id = data.get('session_id', '')
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'session_id is required'
            }, status=400)
        
        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'username and password are required'
            }, status=400)
        
        # Submit credentials (itsr_close returns msg == "NO_SMS_REQUIRED" when SMS is not needed)
        success, msg = submit_credentials(session_id, username, password)

        if not success:
            logger.warning(f"Credentials submission failed for session {session_id}: {msg}")
            return JsonResponse({'success': False, 'error': msg}, status=400)

        # No SMS required: wait for close results and return them directly
        if msg == "NO_SMS_REQUIRED":
            logger.info(f"Session {session_id}: NO_SMS_REQUIRED, waiting for close results")
            result = wait_close_result(session_id, timeout=600)

            # Ensure Django DB reflects closed status for successful tickets
            try:
                closed_numbers = [r.ticket_number for r in result.results if getattr(r, "success", False)]
                if closed_numbers:
                    ITSR_Network.objects.filter(itsr_ticket_number__in=closed_numbers).update(itsr_status='closed')
            except Exception as e:
                logger.warning(f"Failed to update Django DB itsr_status for session {session_id}: {e}")

            requestor_map = _build_requestor_map([r.ticket_number for r in result.results])
            results_list = [{
                'ticket_number': r.ticket_number,
                'requestor': requestor_map.get(r.ticket_number, ''),
                'success': r.success,
                'message': r.message
            } for r in result.results]

            response_data = {
                'success': result.success,
                'needs_sms': False,
                'message': 'Login successful. No SMS verification required.',
                'success_count': result.success_count,
                'fail_count': result.fail_count,
                'total': len(result.results),
                'results': results_list,
            }
            if result.error:
                response_data['error'] = result.error
            return JsonResponse(response_data)

        # SMS required
        logger.info(f"Credentials submitted successfully for session {session_id}, waiting for SMS")
        return JsonResponse({
            'success': True,
            'needs_sms': True,
            'message': 'Login successful. Please check your phone for SMS verification code.'
        })
        
    except Exception as e:
        logger.error(f"Error submitting credentials: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def submit_sms_code_api(request):
    """
    Step 3: Submit SMS verification code and close tickets
    
    POST data:
    {
        "session_id": "abc12345",
        "sms_code": "123456"
    }
    
    Returns:
    {
        "success": true,
        "success_count": 2,
        "fail_count": 0,
        "total": 2,
        "results": [
            {
                "ticket_number": "ITSR001",
                "success": true,
                "message": "关闭成功"
            },
            {
                "ticket_number": "ITSR002",
                "success": true,
                "message": "关闭成功"
            }
        ]
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
        session_id = data.get('session_id', '')
        sms_code = data.get('sms_code', '').strip()
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'session_id is required'
            }, status=400)
        
        if not sms_code:
            return JsonResponse({
                'success': False,
                'error': 'sms_code is required'
            }, status=400)
        
        # Submit SMS code
        result = submit_sms_code(session_id, sms_code)

        # Ensure Django DB reflects closed status for successful tickets
        try:
            closed_numbers = [r.ticket_number for r in result.results if getattr(r, "success", False)]
            if closed_numbers:
                ITSR_Network.objects.filter(itsr_ticket_number__in=closed_numbers).update(itsr_status='closed')
        except Exception as e:
            # Don't fail the API response if DB update fails; log and continue
            logger.warning(f"Failed to update Django DB itsr_status for session {session_id}: {e}")
        
        # Convert result to JSON-serializable format
        requestor_map = _build_requestor_map([r.ticket_number for r in result.results])
        results_list = []
        for r in result.results:
            results_list.append({
                'ticket_number': r.ticket_number,
                'requestor': requestor_map.get(r.ticket_number, ''),
                'success': r.success,
                'message': r.message
            })
        
        response_data = {
            'success': result.success,
            'success_count': result.success_count,
            'fail_count': result.fail_count,
            'total': len(result.results),
            'results': results_list
        }
        
        if result.error:
            response_data['error'] = result.error
        
        logger.info(f"SMS code submitted for session {session_id}: success={result.success}, success_count={result.success_count}, fail_count={result.fail_count}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error submitting SMS code: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def get_session_status_api(request):
    """
    Get current session status
    
    GET/POST with session_id parameter
    
    Returns:
    {
        "success": true,
        "status": "waiting_sms",  // or "waiting_credentials", "logging_in", "closing", "success", "error", "expired"
        "session_id": "abc12345"
    }
    """
    try:
        if request.method == 'POST':
            data = json.loads(request.body) if request.body else {}
            session_id = data.get('session_id', '')
        else:
            session_id = request.GET.get('session_id', '')
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'session_id is required'
            }, status=400)
        
        status = get_session_status(session_id)
        
        if status is None:
            return JsonResponse({
                'success': False,
                'error': 'Session not found or expired',
                'session_id': session_id
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'status': status,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cancel_session_api(request):
    """
    Cancel an active session
    
    POST data:
    {
        "session_id": "abc12345"
    }
    
    Returns:
    {
        "success": true,
        "message": "Session cancelled"
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
        session_id = data.get('session_id', '')
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'session_id is required'
            }, status=400)
        
        cancel_session(session_id)
        
        logger.info(f"Session {session_id} cancelled")
        
        return JsonResponse({
            'success': True,
            'message': 'Session cancelled successfully'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling session: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def update_itsr_status_api(request):
    """
    Update a ticket's ITSR status in the Django DB.

    POST JSON:
    {
        "ticket_id": "123",              // optional
        "ticket_number": "ITSR001",      // optional
        "itsr_status": "open"|"closed"   // required
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}
        ticket_id = str(data.get('ticket_id', '')).strip()
        ticket_number = str(data.get('ticket_number', '')).strip()
        new_status = str(data.get('itsr_status', '')).strip().lower()

        if new_status not in ("open", "closed"):
            return JsonResponse({'success': False, 'error': 'Invalid itsr_status'}, status=400)

        if not ticket_id and not ticket_number:
            return JsonResponse({'success': False, 'error': 'ticket_id or ticket_number is required'}, status=400)

        qs = ITSR_Network.objects.all()
        if ticket_id:
            qs = qs.filter(id=ticket_id)
        else:
            qs = qs.filter(itsr_ticket_number=ticket_number)

        ticket = qs.first()
        if not ticket:
            return JsonResponse({'success': False, 'error': 'Ticket not found'}, status=404)

        ticket.itsr_status = new_status
        ticket.save(update_fields=['itsr_status'])

        return JsonResponse({
            'success': True,
            'ticket_id': ticket.id,
            'ticket_number': ticket.itsr_ticket_number,
            'itsr_status': ticket.itsr_status,
        })
    except Exception as e:
        logger.error(f"Error updating ITSR status: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
