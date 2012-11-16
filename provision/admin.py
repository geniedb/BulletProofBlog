from provision.models import Demo
from django.contrib import admin

class DemoAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['name','organization','email']}),
        ("Status Info", {'fields':['approved','launched','shutdown']}),
        ("Cluster Info", {'fields':['east_coast_dns','west_coast_dns','private_key']})
    ]
    list_display = ('approved','launched','shutdown')
    actions = ['approve', 'launch', 'shutdown']

    def approve(self, request, queryset):
        for d in queryset:
            d.do_approve()

    def launch(self, request, queryset):
        for d in queryset:
            d.do_launch()

    def shutdown(self, request, queryset):
        for d in queryset:
            d.do_shutdown()

admin.site.register(Demo, DemoAdmin)
