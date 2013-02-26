# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Node'
        db.create_table('provision_node', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('instance_id', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('dns', self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True)),
            ('ip', self.gf('django.db.models.fields.IPAddressField')(default='', max_length=15, blank=True)),
            ('type', self.gf('django.db.models.fields.SmallIntegerField')()),
            ('demo', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['provision.Demo'], null=True, on_delete=models.SET_NULL)),
        ))
        db.send_create_signal('provision', ['Node'])

        # Adding model 'Demo'
        db.create_table('provision_demo', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('organization', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75)),
            ('approved', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('launched', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('shutdown', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('provision', ['Demo'])


    def backwards(self, orm):
        # Deleting model 'Node'
        db.delete_table('provision_node')

        # Deleting model 'Demo'
        db.delete_table('provision_demo')


    models = {
        'provision.demo': {
            'Meta': {'object_name': 'Demo'},
            'approved': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'launched': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'organization': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'shutdown': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'provision.node': {
            'Meta': {'object_name': 'Node'},
            'demo': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['provision.Demo']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'dns': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '200', 'blank': 'True'}),
            'ip': ('django.db.models.fields.IPAddressField', [], {'default': "''", 'max_length': '15', 'blank': 'True'}),
            'type': ('django.db.models.fields.SmallIntegerField', [], {})
        }
    }

    complete_apps = ['provision']