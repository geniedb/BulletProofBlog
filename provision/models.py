
import re
import datetime
from argparse import ArgumentParser
from time import sleep
from logging import getLogger
import boto.ec2
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.core.signing import Signer
from django.contrib.sites.models import Site
from tailor.cloudfabric import Cloudfabric
from subprocess import check_call

logger = getLogger(__name__)

DEMO_MESSAGE = """Your CloudFabric Demo has been approved

Please visit http://{domain}{path} to launch your demo.
--
GenieDB
"""

class EC2Regions(object):
    def __init__(self):
        self._regions = {}
    
    def __getitem__(self,key):
        if not self._regions.has_key(key):
            self._regions[key] = boto.ec2.get_region(key).connect()
        return self._regions[key]

class Node(models.Model):
    instance_id = models.CharField("EC2 Instance ID", max_length=200, default="", blank=True)
    dns = models.CharField("EC2 Public DNS Address", max_length=200, default="", blank=True)
    ip = models.IPAddressField("EC2 Instance IP Address", default="", blank=True)
    type = models.SmallIntegerField("EC2 Instance type")
    demo = models.ForeignKey('Demo', null=True, on_delete=models.SET_NULL)

    def __unicode__(self):
        if len(self.dns) == 0:
            return "Instance {id}".format(id=self.instance_id)
        else:
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
        logger.debug("%s: terminating", self)
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

class Demo(models.Model):
    name = models.CharField("Name", max_length=200)
    organization = models.CharField("Organization", max_length=200)
    email = models.EmailField("E-mail")
    approved = models.DateTimeField("Approved", null=True, blank=True)
    launched = models.DateTimeField("Launched", null=True, blank=True)
    shutdown = models.DateTimeField("Shutdown", null=True, blank=True)

    def __unicode__(self):
        return "{name} ({organization}) <{email}>".format(name=self.name, organization=self.organization, email=self.email)

    def get_dns(self):
        return settings.DNS_TEMPLATE.format(demo_id=self.pk)

    @models.permalink
    def get_absolute_url(self):
        return ('provision.views.demo', [Signer().sign(self.pk)])

    def get_haproxy_frontend(self, loadbalencer=None):
        return "\tacl demo{pk}acl hdr(host) -i {dns}\n\tuse_backend demo{pk} if demo{pk}acl".format(
            pk=self.pk,
            dns=self.get_dns()
        )

    def get_haproxy_backend(self, loadbalencer):
        nodeDNS = [(node.type, node.dns) for node in self.node_set.all() if len(node.dns) > 0]
        head = """backend demo{pk}\n\toption\thttpchk HEAD /""".format(pk=self.pk)
        active = ["server demo{pk} {dns}:80 check observe layer7 error-limit 1".format(pk=self.pk, dns=node[1]) for node in nodeDNS if node[0] in loadbalencer['active']]
        backup = ["server demo{pk} {dns}:80 check observe layer7 error-limit 1 backup".format(pk=self.pk, dns=node[1]) for node in nodeDNS if node[0] in loadbalencer['backup']]
        return "\n\t".join([head] + active + backup)

    @classmethod
    def get_haproxy_config(cls, loadbalencer):
        head = """
global
    log /dev/log    local0
    maxconn 4096
    #chroot /usr/share/haproxy
    user haproxy
    group haproxy
    daemon

defaults
    log    global
    mode    http
    option    httplog
    retries    3
    option redispatch
    maxconn    2000
    contimeout    5000
    clitimeout    50000
    srvtimeout    50000

frontend main
    bind    *:80
"""
        frontends = [d.get_haproxy_frontend(loadbalencer) for d in cls.objects.filter(shutdown__exact=None).exclude(launched__exact=None)]
        backends = [d.get_haproxy_backend(loadbalencer) for d in cls.objects.filter(shutdown__exact=None).exclude(launched__exact=None)]
        return "\n".join([head]+frontends+backends)

    @classmethod
    def configure_haproxy(cls):
        for lb in settings.LOADBALENCERS:
            if lb['host'] is not 'localhost':
                raise Exception()
            with open(lb['config'], "w") as f:
                f.write(cls.get_haproxy_config(lb))
                f.write('\n')
            check_call(lb['command'])

    def run_tinc_tailor(self, nodes, commands):
        properties={
            'use_tinc':'false',
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
            logger.debug("%s: running tinc-tailor %s", self, " ".join(n))
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
        logger.info("%s: launching", self)
        self.launched = timezone.now()
        self.shutdown = None
        ec2regions = EC2Regions()
        nodes = [Node(demo=self, type=node_type) for node_type in xrange(len(settings.NODES))]
        [node.do_launch(ec2regions) for node in nodes]
        self.save()
        logger.debug("%s: provisioned %s", self, ",".join(str(node) for node in nodes))
        while True in (node.pending() for node in nodes):
            sleep(15)
        [node.update({'Name':'bullet-proof-blog', 'Customer':str(self)[:255], 'Demo ID':str(self.pk)}) for node in nodes]
        sleep(30)
        logger.debug("%s: instances running", self)
        self.run_tinc_tailor(nodes, [(Cloudfabric,['cloudfabric','refresh'])])
        logger.debug("%s: installed cloudfabric", self)
        self.__class__.configure_haproxy()
        logger.debug("%s: HAProxy configured", self)

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
        logger.info("%s: shutting down", self)
        nodes = self.node_set.all()
        self.shutdown = timezone.now()
        ec2regions = EC2Regions()
        [node.do_terminate(ec2regions) for node in nodes]
        logger.debug("%s: instances terminated", self)
        self.save()
