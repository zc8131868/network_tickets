from django.conf import settings
from django.shortcuts import render


def get_client_ip(request):
    """Get the client's IP address from request headers"""
    # Check for forwarded IP (if behind proxy/load balancer)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the list (client IP)
        ip = x_forwarded_for.split(',')[0].strip()
        return ip
    
    # Check for real IP header
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    
    # Fallback to REMOTE_ADDR
    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr:
        return remote_addr.strip()
    
    return None


def index(request):
    sites = getattr(settings, "NETWORK_SPEED_SITES", [])
    thresholds = getattr(settings, "NETWORK_SPEED_THRESHOLDS", {})
    timeout = getattr(settings, "NETWORK_SPEED_TIMEOUT", 5)
    client_ip = get_client_ip(request)
    
    return render(
        request,
        'index.html',
        {
            "network_speed_sites": sites,
            "network_speed_thresholds": thresholds,
            "network_speed_timeout": timeout,
            "client_ip": client_ip,
        },
    )