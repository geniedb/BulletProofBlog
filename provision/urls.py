from django.conf.urls import patterns, url

urlpatterns = patterns('provision.views',
     url(r'^$', 'request'),
     url(r'^cleanup$', 'shutdown_old'),
     url(r'^demo/(?P<demo_id>\d+:[-\w]+)/$', 'launch')
)
