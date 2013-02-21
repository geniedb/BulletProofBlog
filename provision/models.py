import datetime
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.core.signing import Signer
import boto.ec2
import boto.route53
import boto.route53.record
import re
from tailor.tinc import Tinc
from tailor.cloudfabric import Cloudfabric
from argparse import ArgumentParser
from time import sleep
from django.conf import settings
from GenieDemo.settings import ROUTE53_HOSTED_ZONE

DEMO_MESSAGE = """Your CloudFabric Demo has been approved

Please visit http://{domain}{path} to launch your demo.
--
GenieDB
"""

class R53RecordWithHealthCheck(boto.route53.record.Record):
    def __init__(self, health_check_id, *args, **kwargs):
        super(R53RecordWithHealthCheck,self).__init__( *args, **kwargs)
        self.health_check_id = health_check_id

    def to_xml(self):
        out = super(R53RecordWithHealthCheck,self).to_xml()
        return re.sub('</ResourceRecordSet>',
                      '<HealthCheckId>{0}</HealthCheckId></ResourceRecordSet>'.format(self.health_check_id),
                      out)

def r53_create_heath_check(route53, ip, ref):
    xml_body = """<?xml version="1.0" encoding="UTF-8"?>
<CreateHealthCheckRequest xmlns="https://route53.amazonaws.com/doc/2012-12-12/">
   <CallerReference>{ref}</CallerReference>
   <HealthCheckConfig>
      <IPAddress>{ip}</IPAddress>
      <Type>HTTP</Type>
      <ResourcePath>/cgi-bin/monitor.py</ResourcePath>
   </HealthCheckConfig>
</CreateHealthCheckRequest>""".format(ip=ip, ref=ref)
    response = route53.make_request('POST', '/2012-12-12/healthcheck', {'Content-Type' : 'text/xml'}, xml_body)
    body = response.read()
    boto.log.debug(body)
    if response.status >= 300:
        raise boto.route53.exception.DNSServerError(response.status,
                                       response.reason,
                                       body)
    e = boto.jsonresponse.Element()
    h = boto.jsonresponse.XmlHandler(e, None)
    h.parse(body)
    return e

def r53_delete_heath_check(route53, health_check_id):
    response = route53.make_request('DELETE', '/2012-12-12/healthcheck/{0}'.format(health_check_id))
    body = response.read()
    boto.log.debug(body)
    if response.status >= 300:
        raise boto.route53.exception.DNSServerError(response.status,
                                       response.reason,
                                       body)

class Demo(models.Model):
    name = models.CharField("Name", max_length=200)
    organization = models.CharField("Organization", max_length=200)
    email = models.EmailField("E-mail")
    approved = models.DateTimeField("Approved", null=True, blank=True)
    launched = models.DateTimeField("Launched", null=True, blank=True)
    shutdown = models.DateTimeField("Shutdown", null=True, blank=True)
    east_coast_instance = models.CharField("East Coast EC2 Instance ID", max_length=200, default="", blank=True)
    west_coast_instance = models.CharField("West Coast EC2 Instance ID", max_length=200, default="", blank=True)
    east_coast_health_check = models.CharField("East Coast R53 Health Check ID", max_length=200, default="", blank=True)
    west_coast_health_check = models.CharField("West Coast R53 Health Check ID", max_length=200, default="", blank=True)
    east_coast_dns = models.CharField("East Coast Server DNS Address", max_length=200, default="", blank=True)
    west_coast_dns = models.CharField("West Coast Server DNS Address", max_length=200, default="", blank=True)
    east_coast_ip = models.IPAddressField("East Coast Server IP Address", default="", blank=True)
    west_coast_ip = models.IPAddressField("West Coast Server IP Address", default="", blank=True)

    def __unicode__(self):
        return "{name} ({organization}) <{email}>".format(name=self.name, organization=self.organization, email=self.email)

    @models.permalink
    def get_absolute_url(self):
        return ('provision.views.demo', [Signer().sign(self.pk)])

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
        route53 = boto.connect_route53()
        route53.Version = '2012-12-12'
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
        self.east_coast_ip = east_instance.ip_address
        self.west_coast_ip = west_instance.ip_address
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

        self.east_coast_health_check = r53_create_heath_check(route53, self.east_coast_ip, self.east_coast_instance)['CreateHealthCheckResponse']['HealthCheck']['Id']
        self.west_coast_health_check = r53_create_heath_check(route53, self.west_coast_ip, self.west_coast_instance)['CreateHealthCheckResponse']['HealthCheck']['Id']
        rrs = boto.route53.record.ResourceRecordSets(route53, ROUTE53_HOSTED_ZONE)
        rrs.changes.append(['CREATE', R53RecordWithHealthCheck(self.east_coast_health_check, '{0}.bulletproofblog.geniedb.com'.format(self.pk), 'A', identifier=self.east_coast_instance, weight=1, resource_records=[self.east_coast_ip])])
        rrs.changes.append(['CREATE', R53RecordWithHealthCheck(self.west_coast_health_check, '{0}.bulletproofblog.geniedb.com'.format(self.pk), 'A', identifier=self.west_coast_instance, weight=1, resource_records=[self.west_coast_ip])])
        rrs.ChangeResourceRecordSetsBody = re.sub('https://route53.amazonaws.com/doc/2011-05-05/', 'https://route53.amazonaws.com/doc/2012-12-12/', rrs.ChangeResourceRecordSetsBody)
        rrs.commit()
        self.save()

    def node_info(self, coast):
        if coast == 'east':
            dns = self.east_coast_dns
            instance = self.east_coast_instance
        elif coast == 'west':
            dns = self.east_coast_dns
            instance = self.east_coast_instance
        else:
            raise KeyError()
        properties={
            'use_tinc':'true',
            'netname':'cf',
            'transport':'tcp',
            'hosts_dir': settings.HOSTS_DIR+str(self.pk),
            'key': settings.KEY_FILE
        }
        parser = ArgumentParser()
        subparsers = parser.add_subparsers()
        Cloudfabric.setup_argparse(subparsers.add_parser('cloudfabric'))
        params = parser.parse_args(['cloudfabric', 'status', coast])
        params.hosts = {
            'east': {'connect_to':self.east_coast_dns},
            'west': {'connect_to':self.west_coast_dns}
        }
        params.hosts['west'].update(properties)
        params.hosts['east'].update(properties)
        return {
                'coast': coast,
                'dns': dns,
                'instance': instance,
                'status': Cloudfabric(params, properties).run()
            }
        

    def do_start(self, coast):
        properties={
            'use_tinc':'true',
            'netname':'cf',
            'transport':'tcp',
            'hosts_dir': settings.HOSTS_DIR+str(self.pk),
            'key': settings.KEY_FILE
        }
        parser = ArgumentParser()
        subparsers = parser.add_subparsers()
        Cloudfabric.setup_argparse(subparsers.add_parser('cloudfabric'))
        params = parser.parse_args(['cloudfabric', 'start', coast])
        params.hosts = {
            'east': {'connect_to':self.east_coast_dns},
            'west': {'connect_to':self.west_coast_dns}
        }
        params.hosts['west'].update(properties)
        params.hosts['east'].update(properties)
        Cloudfabric(params, properties).run()


    def do_stop(self, coast):
        properties={
            'use_tinc':'true',
            'netname':'cf',
            'transport':'tcp',
            'hosts_dir': settings.HOSTS_DIR+str(self.pk),
            'key': settings.KEY_FILE
        }
        parser = ArgumentParser()
        subparsers = parser.add_subparsers()
        Cloudfabric.setup_argparse(subparsers.add_parser('cloudfabric'))
        params = parser.parse_args(['cloudfabric', 'stop', coast])
        params.hosts = {
            'east': {'connect_to':self.east_coast_dns},
            'west': {'connect_to':self.west_coast_dns}
        }
        params.hosts['west'].update(properties)
        params.hosts['east'].update(properties)
        Cloudfabric(params, properties).run()

    def do_shutdown(self):
        self.shutdown = timezone.now()
        (east_con, west_con) = self.get_ec2_connections()
        route53 = boto.connect_route53()
        route53.Version = '2012-12-12'
        east_con.terminate_instances([self.east_coast_instance])
        west_con.terminate_instances([self.west_coast_instance])
        rrs = boto.route53.record.ResourceRecordSets(route53, ROUTE53_HOSTED_ZONE)
        rrs.changes.append(['DELETE', R53RecordWithHealthCheck(self.east_coast_health_check, '{0}.bulletproofblog.geniedb.com'.format(self.pk), 'A', identifier=self.east_coast_instance, weight=1, resource_records=[self.east_coast_ip])])
        rrs.changes.append(['DELETE', R53RecordWithHealthCheck(self.west_coast_health_check, '{0}.bulletproofblog.geniedb.com'.format(self.pk), 'A', identifier=self.west_coast_instance, weight=1, resource_records=[self.west_coast_ip])])
        rrs.ChangeResourceRecordSetsBody = re.sub('https://route53.amazonaws.com/doc/2011-05-05/', 'https://route53.amazonaws.com/doc/2012-12-12/', rrs.ChangeResourceRecordSetsBody)
        rrs.commit()
        r53_delete_heath_check(route53, self.east_coast_health_check)
        r53_delete_heath_check(route53, self.west_coast_health_check)
        self.save()
