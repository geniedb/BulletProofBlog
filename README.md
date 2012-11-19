GenieDB CloudFabric Demo
========================

This project allows potential customers to request a two-node CloudFabric clusters. The workflow is:

1. Customer visits the web-page and fills in the request form. They are asked
   to wait for manual approval.
2. An e-mail is sent to the admins.
3. The admins visit the admin panel, review the request, and may then approve
   the request.
4. An e-mail is sent to the customer.
5. The customer clicks the launch button, which causes the EC2 nodes to be
   provisioned and installed.
6. The customer is shown URLs and credentials for the instances.
7. After 1 hour, the instances are terminated.

How to install with apache and mod_wsgi
---------------------------------------

1. Install the pre-requisites, python, paramiko, argparse (if python<=2.6)
   tinc-tailor, django.
2. [Check out the code](https://github.com/geniedb/GenieDemo) to a location
   that is _not_ served by apache.
3. Edit `GenieDemo/settings.py`.  At the very least, set
  * `ADMINS`
  * `DATABSES`
  * `SECRET_KEY`
4. Set up the database by running `python manage.py syncdb`. You will be asked
   to create a user at this point.
5. Add the following, or an approparate variation to Apache configuration:

        WSGIScriptAlias / /path/to/GenieDemo/GenieDemo/wsgi.py
        WSGIPythonPath /path/to/GenieDemo
        <Directory /path/to/GenieDemo/GenieDemo>
            <Files wsgi.py>
                Order deny,allow
                Allow from all
            </Files>
        </Directory>

6. Visit the admin interface (<http://yoursite/admin>) and set up the site
   name by clicking Sites, and editing `example.com`. This is needed so that
   the e-mails have the correct URL.
7. Set up a cron job to visit(<http://yoursite/cleanup>) at least once per
   hour.

How to use the admin interface
------------------------------

The 'Demos' option under 'Provision' is the most important admin interface.
This show a list of all requests for demos. The Approved/Launched/Shutdown
columns show the time when that demo entered the described state, a blank entry
means that demo is still in the previous state.

To change the state of a demo, check the box on the left and select the action
from the drop down, and then click Go. "Approve" will be the main option you
will want, "Launching" is usually done by the customer and "Shutdown" by the
cron job.
