from django.shortcuts import render, get_object_or_404
from provision.models import Demo, Node
from django.core.signing import Signer
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseNotAllowed
from django.core.mail import mail_admins
from django.utils import timezone
import datetime
import json
from django.conf import settings

def request(req):
    try:
        d = Demo(name=req.POST['name'], organization=req.POST['organization'], email=req.POST['email'])
    except:
        return render(req, 'provision/request.html', {'require_approval': settings.REQUIRE_APPROVAL})
    if settings.REQUIRE_APPROVAL:
        d.save()
        mail_admins("New Demo Request", "{demo} has requested a demo.".format(demo=d))
    else:
        d.do_approve(False)
        d.do_launch()
    return HttpResponseRedirect(d.get_absolute_url())

def demo(req, demo_id):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.launchable() and req.method == 'POST':
        d.do_launch()
    if d.shutdown is not None:
        return render(req,'provision/shutdown.html', {'demo': d})
    elif d.launched is not None:
        return render(req,'provision/running.html', {'demo': d, 'nodes': d.node_set.all()})
    elif d.approved is not None:
        return render(req,'provision/launch.html', {'demo': d})
    else:
        return render(req,'provision/awaiting_approval.html', {'demo': d})

def node(req, demo_id, node_type):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.shutdown is not None or d.launched is None:
        return HttpResponseForbidden("Demo not running.")
    n = get_object_or_404(Node, demo=d, type=node_type)

    if req.method == "GET":
        return HttpResponse(json.dumps(d.node_info(n)), mimetype="application/json")
    elif req.method == "POST":
        if not req.POST.has_key('action'):
            return HttpResponseForbidden("Invalid action.")
        if req.POST['action'] == "start":
            d.do_start(n)
        elif req.POST['action'] == "stop":
            d.do_stop(n)
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
