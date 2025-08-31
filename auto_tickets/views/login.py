from django.shortcuts import render
from auto_tickets.views.forms_login import UserForm
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout


def login_view(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None and user.is_active:
            auth_login(request, user)

            request.session['first_name'] = user.first_name

            next_url = request.GET.get('next', '/')

            return HttpResponseRedirect(next_url)
        
        else:
            return render(request, 'login.html', {'form': form, 'error': 'Invalid username or password'})

    
    else:
        if request.user.is_authenticated:
            return HttpResponseRedirect('/')
        else:
            form = UserForm()
            return render(request, 'login.html', {'form': form})
        
def logout_view(request):
    auth_logout(request)
    return HttpResponseRedirect('/accounts/login/')