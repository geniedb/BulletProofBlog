from django.shortcuts import render, get_object_or_404
from provision.models import Demo
from django.core.signing import Signer
from django.http import HttpResponseRedirect
from django.core.mail import mail_admins

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
    if d.launchable and req.method == 'POST':
        d.launch()
    if d.launched is not None:
        return render(req,'provision/launched.html', {'demo': d})
    else:
        return render(req,'provision/launch.html', {'demo': d})