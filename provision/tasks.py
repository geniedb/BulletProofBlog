#!/usr/bin/python

from celery.task import task

@task()
def launch(demo):
    try:
        demo.do_launch()
    except:
        demo.status = demo.ERROR
        demo.save()
        raise