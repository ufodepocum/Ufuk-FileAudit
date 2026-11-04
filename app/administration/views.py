from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import APIToken

@user_passes_test(lambda u: u.is_active and u.is_staff)
def list_users(request):
    users = User.objects.all()
    return render(request, 'administration/list_users.html', {'users': users})

@user_passes_test(lambda u: u.is_active and u.is_staff)
def disable_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = False  # Disable the user
    user.save()
    return redirect('administration:users')

@user_passes_test(lambda u: u.is_active and u.is_staff)
def enable_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True  # Enable the user
    user.save()
    return redirect('administration:users')

@user_passes_test(lambda u: u.is_active and u.is_staff)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('administration:users')

@user_passes_test(lambda u: u.is_active and u.is_staff)
def create_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('administration:users')
    else:
        form = CustomUserCreationForm()
    return render(request, 'administration/create_user.html', {'form': form})

@user_passes_test(lambda u: u.is_active and u.is_staff)
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('administration:users')
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'administration/edit_user.html', {'form': form, 'user_id': user_id})
