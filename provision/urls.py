from django.conf.urls import patterns, url

urlpatterns = patterns('provision.views',
     url(r'^$', 'request'),
     url(r'^cleanup$', 'shutdown_old'),
     url(r'^launch/(?P<demo_id>\d+:[-\w]+)/$', 'launch')
)
