from django.shortcuts import render, get_object_or_404
from provision.models import Demo, Node
from provision.tasks import launch
from django.core.signing import Signer
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseNotAllowed, HttpResponseServerError
from django.utils import timezone
import datetime
import json
from logging import getLogger
from django.conf import settings

logger = getLogger(__name__)

def request(req):
    try:
        d = Demo(email=req.POST['email'])
    except:
        return render(req, 'provision/request.html', {'require_approval': settings.REQUIRE_APPROVAL})
    if settings.REQUIRE_APPROVAL:
        logger.info("%s: new demo request", d)
        d.do_request_approval()
    else:
        d.do_approve(False)
        if req.REQUEST.has_key('format') and req.REQUEST['format'] == 'json':
            launch.delay(d)
            return HttpResponse(json.dumps(d.demo_info()), mimetype="application/json")
        else:
            d.do_launch()
    return HttpResponseRedirect(d.get_absolute_url())

def demo(req, demo_id):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.launchable() and req.method == 'POST' :
        if req.REQUEST.has_key('format') and req.REQUEST['format'] == 'json':
            launch.delay(d)
        else:
            d.do_launch()

    if req.REQUEST.has_key('format') and req.REQUEST['format'] == 'json':
        return HttpResponse(json.dumps(d.demo_info()), mimetype="application/json")

    if d.status in (Demo.SHUTTING_DOWN, Demo.OVER):
        return render(req,'provision/shutdown.html', {'demo': d})
    elif d.status == Demo.RUNNING:
        return render(req,'provision/running.html', {'demo': d, 'nodes': d.node_set.all().order_by('type')})
    elif d.status == Demo.AWAITING_LAUNCH:
        return render(req,'provision/launch.html', {'demo': d})
    elif d.status == Demo.AWAITING_APPROVAL:
        return render(req,'provision/awaiting_approval.html', {'demo': d})
    else:
        return HttpResponseServerError("Demo status: %s" %d.get_status_display())

def node(req, demo_id, node_type):
    demo_id=Signer().unsign(demo_id)
    d = get_object_or_404(Demo, pk=demo_id)
    if d.status is not Demo.RUNNING:
        return HttpResponseForbidden("Demo not running.")
    n = get_object_or_404(Node, demo=d, type=node_type)

    if req.method not in ('POST','GET'):
        return HttpResponseNotAllowed('POST','GET')
    if req.method == "POST":
        if not req.POST.has_key('action'):
            return HttpResponseForbidden("Invalid action.")
        if req.POST['action'] == "start":
            d.do_start(n)
        elif req.POST['action'] == "stop":
            d.do_stop(n)
        else:
            return HttpResponseForbidden("Invalid action.")
    if req.REQUEST.has_key('format') and req.REQUEST['format'] == 'json':
        return HttpResponse(json.dumps(d.node_info(n)), mimetype="application/json")
    else:
        return HttpResponseRedirect(d.get_absolute_url())

def shutdown_old(req):
    # doesn't require perms
    for d in Demo.objects.filter(status__lt=Demo.SHUTTING_DOWN, launched__lte=timezone.now() - datetime.timedelta(hours=1)):
        try:
            logger.info("%s: shutting down during cleanup", d)
            d.do_shutdown()
        except:
            logger.exception("%s: Cloud not shutdown during cleanup", d)
    return HttpResponse()
