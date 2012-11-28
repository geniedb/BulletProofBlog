import datetime
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.core.signing import Signer
import boto.ec2
from tailor.tinc import Tinc
from tailor.cloudfabric import Cloudfabric
from argparse import ArgumentParser
from time import sleep
from django.conf import settings

DEMO_MESSAGE = """Your CloudFabric Demo has been approved

Please visit http://{domain}{path} to launch your demo.
--
GenieDB
"""

class Demo(models.Model):
    name = models.CharField("Name", max_length=200)
    organization = models.CharField("Organization", max_length=200)
    email = models.EmailField("E-mail")
    approved = models.DateTimeField("Approved", null=True, blank=True)
    launched = models.DateTimeField("Launched", null=True, blank=True)
    shutdown = models.DateTimeField("Shutdown", null=True, blank=True)
    east_coast_instance = models.CharField("East Coast Instance ID", max_length=200, default="", blank=True)
    west_coast_instance = models.CharField("West Coast Instance ID", max_length=200, default="", blank=True)
    east_coast_dns = models.CharField("East Coast Server DNS Address", max_length=200, default="", blank=True)
    west_coast_dns = models.CharField("West Coast Server DNS Address", max_length=200, default="", blank=True)

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

    def get_ec2_connections(self):
        return( boto.connect_ec2(), boto.ec2.regions()[4].connect())

    def do_launch(self):
        self.launched = timezone.now()
        self.shutdown = None

        # Provision Servers
        (east_con, west_con) = self.get_ec2_connections()
        east_res = east_con.run_instances(
            settings.EAST_AMI,
            key_name=settings.EAST_KEY_NAME,
            instance_type=settings.EAST_SIZE,
            security_groups=settings.EAST_SECURITY_GROUPS
        )
        east_instance = east_res.instances[0]
        self.east_coast_instance = east_instance.id
        self.save()
        west_res = west_con.run_instances(
            settings.WEST_AMI,
            key_name=settings.WEST_KEY_NAME,
            instance_type=settings.WEST_SIZE,
            security_groups=settings.WEST_SECURITY_GROUPS
        )
        west_instance = west_res.instances[0]
        self.west_coast_instance = west_instance.id
        self.save()

        # Wait for nodes to come up
        while east_instance.update() == 'pending' or west_instance.update() == 'pending':
            sleep(30)
        self.east_coast_dns = east_instance.public_dns_name
        self.west_coast_dns = west_instance.public_dns_name
        self.save()
        east_instance.add_tag("Name", "east-generic-noel")
        east_instance.add_tag("Started For", str(self)[:255])
        east_instance.add_tag("Demo ID", str(self.pk))
        west_instance.add_tag("Name", "west-generic-noel")
        west_instance.add_tag("Started For", str(self)[:255])
        west_instance.add_tag("Demo ID", str(self.pk))

        # Install CloudFabric
        properties={
            'use_tinc':'true',
            'netname':'cf',
            'transport':'tcp',
            'hosts_dir': settings.HOSTS_DIR+str(self.pk),
            'key': settings.KEY_FILE
        }
        parser = ArgumentParser()
        subparsers = parser.add_subparsers()
        Tinc.setup_argparse(subparsers.add_parser('tinc'))
        Cloudfabric.setup_argparse(subparsers.add_parser('cloudfabric'))
        for m,n in ((Tinc,['tinc','install']), (Cloudfabric,['cloudfabric','refresh'])):
            params = parser.parse_args(n)
            params.hosts = {
                'east': {'connect_to':self.east_coast_dns},
                'west': {'connect_to':self.west_coast_dns}
            }
            params.hosts['west'].update(properties)
            params.hosts['east'].update(properties)
            m(params, properties).run()

    def do_shutdown(self):
        self.shutdown = timezone.now()
        (east_con, west_con) = self.get_ec2_connections()
        east_con.terminate_instances([self.east_coast_instance])
        west_con.terminate_instances([self.west_coast_instance])
        self.save()
