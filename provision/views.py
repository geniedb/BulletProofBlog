from django.shortcuts import render, get_object_or_404
from provision.models import Demo
from django.core.signing import Signer
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseNotAllowed
from django.core.mail import mail_admins
from django.utils import timezone
import datetime
import json

def request(req):
    try:
        d = Demo(name=req.POST['name'], organization=req.POST['organization'], email=req.POST['email'])
    except:
        return render(req, 'provision/request.html')
    d.save()
    mail_admins("New Demo Request", "{demo} has requested a demo.".format(demo=d))
    return HttpResponseRedirect(d.get_absolute_url())

def demo(req, demo_id):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.launchable() and req.method == 'POST':
        d.do_launch()
    if d.shutdown is not None:
        return render(req,'provision/shutdown.html', {'demo': d})
    elif d.launched is not None:
        return render(req,'provision/running.html', {'demo': d})
    elif d.approved is not None:
        return render(req,'provision/launch.html', {'demo': d})
    else:
        return render(req,'provision/awaiting_approval.html', {'demo': d})

def node(req, demo_id, node_id):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.shutdown is not None or d.launched is None:
        return HttpResponseForbidden("Demo not running.")
    if node_id not in ("east","west"):
        return HttpResponseForbidden("Invalid node.")

    if req.method == "GET":
        return HttpResponse(json.dumps(d.node_info(node_id)), mimetype="application/json")
    elif req.method == "POST":
        if not req.POST.has_key('action'):
            return HttpResponseForbidden("Invalid action.")
        if req.POST['action'] == "start":
            d.do_start(node_id)
        elif req.POST['action'] == "stop":
            d.do_stop(node_id)
        else:
            return HttpResponseForbidden()
        return HttpResponseRedirect(d.get_absolute_url())
    else:
        return HttpResponseNotAllowed('POST','GET')

def shutdown_old(req):
    # doesn't require perms
    for d in Demo.objects.filter(shutdown__exact=None, launched__lte=timezone.now() - datetime.timedelta(hours=1)):
        d.do_shutdown()
    return HttpResponse()
