from django.contrib import admin

from projects.models import APIKey, Project


admin.site.register(Project)
admin.site.register(APIKey)
