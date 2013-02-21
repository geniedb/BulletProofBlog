
import re
import datetime
from argparse import ArgumentParser
from time import sleep
import boto.ec2
import boto.route53.record
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.core.signing import Signer
from django.contrib.sites.models import Site
from tailor.tinc import Tinc
from tailor.cloudfabric import Cloudfabric

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
      <ResourcePath>/cgi-bin/monitor.py?format=json</ResourcePath>
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

class EC2Regions(object):
    def __init__(self):
        self._regions = {}
    
    def __getitem__(self,key):
        if not self._regions.has_key(key):
            self._regions[key] = boto.ec2.get_region(key).connect()
        return self._regions[key]

class Node(models.Model):
    instance_id = models.CharField("EC2 Instance ID", max_length=200, default="", blank=True)
    health_check = models.CharField("R53 Health Check ID", max_length=200, default="", blank=True)
    dns = models.CharField("EC2 Public DNS Address", max_length=200, default="", blank=True)
    ip = models.IPAddressField("EC2 Instance IP Address", default="", blank=True)
    type = models.SmallIntegerField("EC2 Instance type")
    demo = models.ForeignKey('Demo', null=True, on_delete=models.SET_NULL)

    def __unicode__(self):
        return "Instance {id} at {dns}".format(id=self.instance_id, dns=self.dns)

    @models.permalink
    def get_absolute_url(self):
        return ('provision.views.node', [Signer().sign(self.demo.pk), self.type])

    def do_launch(self, ec2regions):
        node_type = settings.NODES[self.type]
        res = ec2regions[node_type['REGION']].run_instances(
            node_type['AMI'],
            key_name=node_type['KEY_NAME'],
            instance_type=node_type['SIZE'],
            security_groups=node_type['SECURITY_GROUPS']
        )
        self.instance = res.instances[0]
        self.instance_id = self.instance.id
        self.save()

    def do_terminate(self, ec2regions):
        ec2regions[settings.NODES[self.type]['REGION']].terminate_instances([self.instance_id])
        self.delete()

    def pending(self):
        return self.instance.update()=='pending'

    def update(self, tags={}):
        self.dns = self.instance.public_dns_name
        self.ip = self.instance.ip_address
        self.save()
        for k,v in tags.items():
            self.instance.add_tag(k, v)

    def get_r53_rr(self):
        return R53RecordWithHealthCheck(
            self.health_check,
            settings.DNS_TEMPLATE.format(demo_id=self.demo.pk),
            'A',
            ttl=30,
            identifier=self.instance_id,
            weight=1,
            resource_records=[self.ip]
        )

    def create_health_check(self,route53):
        self.health_check = r53_create_heath_check(route53, self.ip, self.instance_id)['CreateHealthCheckResponse']['HealthCheck']['Id']
        self.save()

    def delete_health_check(self,route53):
        self.health_check = r53_delete_heath_check(route53, self.health_check)

class Demo(models.Model):
    name = models.CharField("Name", max_length=200)
    organization = models.CharField("Organization", max_length=200)
    email = models.EmailField("E-mail")
    approved = models.DateTimeField("Approved", null=True, blank=True)
    launched = models.DateTimeField("Launched", null=True, blank=True)
    shutdown = models.DateTimeField("Shutdown", null=True, blank=True)

    def __unicode__(self):
        return "{name} ({organization}) <{email}>".format(name=self.name, organization=self.organization, email=self.email)

    @models.permalink
    def get_absolute_url(self):
        return ('provision.views.demo', [Signer().sign(self.pk)])

    def run_tinc_tailor(self, nodes, commands):
        properties={
            'use_tinc':'true',
            'netname':'cf',
            'transport':'tcp',
            'hosts_dir': settings.HOSTS_DIR+str(self.pk),
            'key': settings.KEY_FILE
        }
        parser = ArgumentParser()
        subparsers = parser.add_subparsers()
        for m,n in commands:
            m.setup_argparse(subparsers.add_parser(n[0]))
        last_res = None
        for m,n in commands:
            params = parser.parse_args(n)
            params.hosts = dict(
                ('node_{0}'.format(i), {'connect_to':nodes[i].dns}) for i in xrange(len(nodes))
            )
            [x.update(properties) for x in params.hosts.values()]
            last_res = m(params, properties).run()
        return last_res

    def due_to_shudown(self):
        return self.launched <= timezone.now() - datetime.timedelta(hours=1)

    def launchable(self):
        return self.approved is not None and self.launched is None

    def do_approve(self, email=True):
        self.approved = timezone.now()
        if email:
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
        ec2regions = EC2Regions()
        route53 = boto.connect_route53()
        route53.Version = '2012-12-12'
        nodes = [Node(demo=self, type=node_type) for node_type in xrange(len(settings.NODES))]
        [node.do_launch(ec2regions) for node in nodes]
        self.save()
        while True in (node.pending() for node in nodes):
            sleep(15)
        [node.update({'Name':'bullet-proof-blog', 'Customer':str(self)[:255], 'Demo ID':str(self.pk)}) for node in nodes]

        # Install CloudFabric
        self.run_tinc_tailor(nodes, ((Tinc,['tinc','install']), (Cloudfabric,['cloudfabric','refresh'])))
        [node.create_health_check(route53) for node in nodes]
        rrs = boto.route53.record.ResourceRecordSets(route53, settings.ROUTE53_HOSTED_ZONE)
        [rrs.changes.append(['CREATE', node.get_r53_rr()]) for node in nodes]
        rrs.ChangeResourceRecordSetsBody = re.sub('https://route53.amazonaws.com/doc/2011-05-05/', 'https://route53.amazonaws.com/doc/2012-12-12/', rrs.ChangeResourceRecordSetsBody)
        rrs.commit()
        self.save()

    def node_info(self, node):
        nodes = self.node_set.all()
        return {
                'node_id': node.type,
                'status': self.run_tinc_tailor(nodes, [[Cloudfabric,['cloudfabric', 'status', 'node_{0}'.format(node.type)]]])
            }
        

    def do_start(self, node):
        nodes = self.node_set.all()
        self.run_tinc_tailor(nodes, [[Cloudfabric,['cloudfabric', 'start', 'node_{0}'.format(node.type)]]])


    def do_stop(self, node):
        nodes = self.node_set.all()
        self.run_tinc_tailor(nodes, [[Cloudfabric,['cloudfabric', 'stop', 'node_{0}'.format(node.type)]]])

    def do_shutdown(self):
        nodes = self.node_set.all()
        self.shutdown = timezone.now()
        ec2regions = EC2Regions()
        route53 = boto.connect_route53()
        route53.Version = '2012-12-12'
        [node.do_terminate(ec2regions) for node in nodes]
        rrs = boto.route53.record.ResourceRecordSets(route53, settings.ROUTE53_HOSTED_ZONE)
        [rrs.changes.append(['DELETE', node.get_r53_rr()]) for node in nodes]
        rrs.ChangeResourceRecordSetsBody = re.sub('https://route53.amazonaws.com/doc/2011-05-05/', 'https://route53.amazonaws.com/doc/2012-12-12/', rrs.ChangeResourceRecordSetsBody)
        rrs.commit()
        [node.delete_health_check(route53) for node in nodes]
        self.save()
