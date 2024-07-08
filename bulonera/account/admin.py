from django.contrib import admin
from .models import Account, UserProfileAdmin, UserProfile, AccountAdmin

# Register your models here.
admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
