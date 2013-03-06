from provision.models import Demo, Node
from django.contrib import admin


class NodeInline(admin.StackedInline):
    model=Node
    extra=0

class DemoAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['email', 'status', 'launched']}),
    ]
    inlines = [NodeInline]
    list_display = ('__unicode__', 'status')
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
admin.site.register(Node)
