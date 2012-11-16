import datetime
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.core.signing import Signer

DEMO_MESSAGE = """Your CloudFabric Demo has been approved

Please visit http://{domain}{path} to launch your demo.
--
GenieDB
"""

class Demo(models.Model):
    name = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    email = models.EmailField()
    approved = models.DateTimeField("Approved", null=True, blank=True)
    launched = models.DateTimeField("Launched", null=True, blank=True)
    shutdown = models.DateTimeField("Shutdown", null=True, blank=True)
    east_coast_dns = models.CharField(max_length=200, default="", blank=True)
    west_coast_dns = models.CharField(max_length=200, default="", blank=True)
    private_key = models.CharField(max_length=2000, default="", blank=True)

    def __unicode__(self):
        return "{name} ({organization}) <{email}>".format(name=self.name, organization=self.organization, email=self.email)

    @models.permalink
    def get_absolute_url(self):
        return ('provision.views.launch', [Signer().sign(self.pk)])

    def due_to_shudown(self):
        return self.launched <= timezone.now() - datetime.timedelta(hours=1)

    def launchable(self):
        return self.approved is not None and self.launched is None

    def do_approve(self):
        self.approved = timezone.now()
        send_mail("CloudFabric Demo Ready",
                  DEMO_MESSAGE.format(domain=Site.objects.get_current().domain, path=self.get_absolute_url()),
                  'tech@geniedb.com',
                  [self.email])
        self.save()

    def do_launch(self):
        self.launched = timezone.now()
        #Launch The cluster!
        self.east_coast_dns = "dns"
        self.west_coast_dns = "dns2"
        self.private_key = "--PRIVATE KEY--"
        self.save()

    def do_shutdown(self):
        self.shutdown = timezone.now()
        #Shutdown the cluster
        self.save()
