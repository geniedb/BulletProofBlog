#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from urlparse import parse_qs, urlparse
from subprocess import check_call
import hmac

SERVER_ADDRESS = ''
SERVER_PORT = 8000
HMAC_KEY = 'xxx'
CFG = '/etc/haproxy/bpb.cfg'
CMD = ['sudo', '/etc/init.d/haproxy', 'reload']

class HAProxyService(BaseHTTPRequestHandler):
    def start(self):
        (_,_,self.file,_,self.qs,_) = urlparse(self.path)
        self.qs = parse_qs(self.qs)
        self.upload = self.rfile.read(int(self.headers.getheader('content-length')))
    
    def verify_hmac(self):
        if not self.qs.has_key('hmac'):
            return False
        h = hmac.new(HMAC_KEY)
        h.update(self.upload)
        if h.hexdigest() != self.qs['hmac'][0]:
            return False
        return True

    def write_cfg(self):
        with open(CFG, "w") as f:
            f.write(self.upload)

    def restart(self):
        check_call(CMD)

    def do_POST(self):
        self.start()
        if not self.verify_hmac():
            self.send_error(403, "HMAC verification failed")
            return
        try:
            self.write_cfg()
        except:
            self.send_error(500, "Could not write cfg file")
            return
        try:
            self.restart()
        except:
            self.send_error(500, "Could not restart service")
            return
        self.send_response(204)
        self.end_headers()
        return

if __name__ == '__main__':
    HTTPServer((SERVER_ADDRESS, SERVER_PORT), HAProxyService).serve_forever()