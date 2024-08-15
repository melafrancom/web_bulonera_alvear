from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
#Local Apps:
from .models import Account, UserProfile


class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)
    
    #Necesario para el UserAdmin.
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()


class UserProfileAdmin(admin.ModelAdmin): #define cómo se mostrarán los objetos UserProfile del admin.
    def thumbnail(self, object):
        return format_html('<img src="{}" width="30" style="border-radius=50%;" >'.format(object.profile_picture.url))
    
    thumbnail.short_description = 'imagen de perfil'
    list_display = ('thumbnail', 'profile_picture', 'user', 'city', 'state', 'country')
    

    
# Register your models here.
admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
