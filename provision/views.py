from django.shortcuts import render, get_object_or_404
from provision.models import Demo
from django.core.signing import Signer
from django.http import HttpResponseRedirect, HttpResponse
from django.core.mail import mail_admins
from django.utils import timezone
import datetime

def request(req):
    try:
        d = Demo(name=req.POST['name'], organization=req.POST['organization'], email=req.POST['email'])
    except:
        return render(req, 'provision/request.html')
    d.save()
    mail_admins("New Demo Request", "{demo} has requested a demo.".format(demo=d))
    return HttpResponseRedirect('launch/'+Signer().sign(d.pk))

def launch(req, demo_id):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.launchable() and req.method == 'POST':
        d.do_launch()
    if d.launched is not None:
        return render(req,'provision/launched.html', {'demo': d})
    else:
        return render(req,'provision/launch.html', {'demo': d})

def shutdown_old(req):
    # doesn't require perms
    for d in Demo.objects.filter(shutdown__exact=None, launched__lte=timezone.now() - datetime.timedelta(hours=1)):
        d.do_shutdown()
    return HttpResponse()
