from provision.models import Demo
from django.contrib import admin
from django.utils import timezone

class DemoAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['name','organization','email']}),
        ("Status Info", {'fields':['approved','launched','shutdown']}),
        ("Cluster Info", {'fields':['east_coast_dns','west_coast_dns','private_key']})
    ]
    list_display = ('approved','launched','shutdown')
    actions = ['approve']

    def approve(self, request, queryset):
        queryset.update(approved=timezone.now())

admin.site.register(Demo, DemoAdmin)