from django import forms
from core.models import NotificationSettings, User


class AvatarUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar']
        