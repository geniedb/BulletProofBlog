# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Demo.status'
        db.add_column('provision_demo', 'status',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Demo.status'
        db.delete_column('provision_demo', 'status')


    models = {
        'provision.demo': {
            'Meta': {'object_name': 'Demo'},
            'approved': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'launched': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'shutdown': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'})
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