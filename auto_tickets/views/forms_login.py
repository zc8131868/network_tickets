from django import forms


class UserForm(forms.Form):
    username = forms.CharField(label='Username',
                               max_length=100,
                               required=True,
                               widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"})
                               )
    password = forms.CharField(label='Password',
                               max_length=100,
                               required=True,
                               widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"})
                               )
