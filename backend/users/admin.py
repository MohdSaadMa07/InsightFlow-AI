from django.contrib import admin

from users.models import Organization, User


admin.site.register(Organization)
admin.site.register(User)
