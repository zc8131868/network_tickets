"""
ITSR Authentication Views for Web Interface
Handles client-side browser authentication flow
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
import json
import logging
import time
import re

logger = logging.getLogger(__name__)


def parse_sms_content(sms_text):
    """
    Parse SMS content to extract authentication tokens.
    
    Supports multiple formats:
    1. Key-value pairs:
       SY_ACCESS_TOKEN: eyJhbGciOiJIUzI1NiIsInR...
       SY_UID: 12345
       sy-cinfo: C4wfMXAR9mXTBKV1LQuL1w==
    
    2. JSON format:
       {"SY_ACCESS_TOKEN": "...", "SY_UID": "...", "sy-cinfo": "..."}
    
    Args:
        sms_text: Raw SMS text content
        
    Returns:
        dict: Parsed tokens with keys: access_token, uid, sy_cinfo
    """
    if not sms_text or not sms_text.strip():
        return None
    
    sms_text = sms_text.strip()
    tokens = {}
    
    # Try JSON format first
    try:
        json_data = json.loads(sms_text)
        tokens['access_token'] = json_data.get('SY_ACCESS_TOKEN') or json_data.get('access_token') or json_data.get('SY_ACCESS_TOKEN')
        tokens['uid'] = json_data.get('SY_UID') or json_data.get('uid')
        tokens['sy_cinfo'] = json_data.get('sy-cinfo') or json_data.get('sy_cinfo') or json_data.get('SY_CINFO')
        
        if tokens.get('access_token') and tokens.get('uid'):
            return tokens
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Try key-value format
    # Pattern: KEY: VALUE or KEY=VALUE
    lines = sms_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try KEY: VALUE format
        match = re.match(r'^([A-Za-z_-]+)[:\s=]+(.+)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            
            if key.upper() in ['SY_ACCESS_TOKEN', 'ACCESS_TOKEN']:
                tokens['access_token'] = value
            elif key.upper() in ['SY_UID', 'UID']:
                tokens['uid'] = value
            elif key.lower() in ['sy-cinfo', 'sy_cinfo', 'sycinfo']:
                tokens['sy_cinfo'] = value
    
    # Return tokens if we have at least access_token and uid
    if tokens.get('access_token') and tokens.get('uid'):
        return tokens
    
    return None


@login_required
@require_http_methods(["GET"])
def itsr_auth_page(request):
    """
    Special page that opens in popup window.
    Shows instructions and redirects to BPM login.
    """
    # Store return URL in session
    return_url = request.GET.get('return_url', '/ticket_detail_search/')
    request.session['itsr_return_url'] = return_url
    
    callback_url = request.build_absolute_uri('/itsr_auth_callback/')
    bpm_url = 'https://bpm.cmhktry.com/main/portal/ctp-affair/affairPendingCenter?portletTitle=%E5%BE%85%E8%BE%A6%E4%BA%8B%E9%A0%85'
    
    return render(request, 'itsr_auth_page.html', {
        'bpm_url': bpm_url,
        'callback_url': callback_url
    })


@login_required
@require_http_methods(["GET"])
def itsr_token_extractor(request):
    """
    Helper page to extract tokens from BPM session.
    Can be opened in a new tab while BPM is open.
    """
    return render(request, 'itsr_token_extractor.html')


@login_required
@csrf_exempt
@xframe_options_exempt
@require_http_methods(["GET", "POST"])
def itsr_auth_callback(request):
    """
    Callback page that extracts auth tokens from BPM session.
    This page should be loaded in an iframe or popup after user logs into BPM.
    Uses JavaScript to extract tokens from cookies/localStorage and send to server.
    """
    if request.method == 'POST':
        # Receives auth tokens via POST from JavaScript
        logger.info(f"ITSR auth callback POST received from user {request.user.username}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Request body length: {len(request.body)}")
        
        try:
            # Parse JSON data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            access_token = data.get('access_token', '')
            uid = data.get('uid', '')
            sy_cinfo = data.get('sy_cinfo', '')
            
            logger.info(f"Received access_token length: {len(access_token) if access_token else 0}")
            logger.info(f"Received uid: {uid}")
            
            # Store in session
            if access_token and uid:
                request.session['itsr_access_token'] = access_token
                request.session['itsr_uid'] = uid
                request.session['itsr_sy_cinfo'] = sy_cinfo or 'C4wfMXAR9mXTBKV1LQuL1w=='
                request.session['itsr_auth_time'] = str(int(time.time()))
                
                logger.info(f"ITSR auth stored in session for user {request.user.username}")
                logger.info(f"Session keys: {list(request.session.keys())}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Authentication successful'
                })
            else:
                logger.warning(f"Missing tokens - access_token: {bool(access_token)}, uid: {bool(uid)}")
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required authentication tokens'
                }, status=400)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in ITSR auth callback: {str(e)}")
            logger.error(f"Request body: {request.body[:200]}")
            return JsonResponse({
                'success': False,
                'message': f'Invalid JSON: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in ITSR auth callback: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=500)
    else:
        # GET request - show page that extracts tokens
        callback_url = request.build_absolute_uri('/itsr_auth_callback/')
        return render(request, 'itsr_auth_callback.html', {
            'callback_url': callback_url
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def itsr_auth_sms_callback(request):
    """
    Handle SMS-based authentication.
    Receives SMS content, parses tokens, and stores them in session.
    """
    logger.info(f"ITSR SMS auth callback POST received from user {request.user.username}")
    
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            sms_content = data.get('sms_content', '')
        else:
            sms_content = request.POST.get('sms_content', '')
        
        if not sms_content:
            return JsonResponse({
                'success': False,
                'message': 'SMS content is required'
            }, status=400)
        
        # Parse SMS content to extract tokens
        parsed_tokens = parse_sms_content(sms_content)
        
        if not parsed_tokens:
            logger.warning(f"Failed to parse tokens from SMS content")
            return JsonResponse({
                'success': False,
                'message': 'Failed to parse authentication tokens from SMS. Please check the format.'
            }, status=400)
        
        access_token = parsed_tokens.get('access_token', '')
        uid = parsed_tokens.get('uid', '')
        sy_cinfo = parsed_tokens.get('sy_cinfo', 'C4wfMXAR9mXTBKV1LQuL1w==')
        
        # Validate tokens
        if not access_token or not uid:
            return JsonResponse({
                'success': False,
                'message': 'Missing required tokens (access_token or uid)'
            }, status=400)
        
        # Store in session
        request.session['itsr_access_token'] = access_token
        request.session['itsr_uid'] = uid
        request.session['itsr_sy_cinfo'] = sy_cinfo
        request.session['itsr_auth_time'] = str(int(time.time()))
        
        logger.info(f"ITSR auth stored in session from SMS for user {request.user.username}")
        logger.info(f"Token length: {len(access_token)}, UID: {uid[:10] if len(uid) > 10 else uid}")
        
        return JsonResponse({
            'success': True,
            'message': 'Authentication successful'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in SMS auth callback: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Invalid JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in SMS auth callback: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def itsr_check_auth(request):
    """
    Check if user has valid ITSR auth in session.
    Returns JSON response.
    """
    has_auth = (
        'itsr_access_token' in request.session and 
        'itsr_uid' in request.session
    )
    
    return JsonResponse({
        'has_auth': has_auth,
        'auth_time': request.session.get('itsr_auth_time', '')
    })
