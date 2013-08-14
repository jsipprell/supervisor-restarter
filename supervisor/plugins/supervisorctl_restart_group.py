# Copyright 2013 Jesse Sipprell <jessesipprell@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""supervisorctl_restart_group -- perform a fast restart of a supervisor process group.

Usage: %s <group>

This script performs an xml rpc call to a supervisord server and requests a fast restart
of an entire process group.

The supervisord server must be configured to use the restarter plugin.
"""
import sys,socket,errno
import xmlrpclib
from supervisor.options import ClientOptions

class Controller(object):
  def __init__(self,options,stdout=sys.stdout,stderr=sys.stderr,stdin=sys.stdin):
    super(Controller,self).__init__()
    self.options = options
    self.stdout = stdout
    self.stderr = stderr
    self.stdin = stdin

  def output(self, *lines):
    lines = list(lines)
    for i,line in enumerate(lines):
      if isinstance(line,unicode):
        lines[i] = line.encode('utf-8')
    self.stdout.write('\n'.join(lines))
    self.stdout.write('\n')

  def output_error(self, *lines):
    lines = list(lines)
    for i,line in enumerate(lines):
      if isinstance(line,unicode):
        lines[i] = line.encode('utf-8')
    self.stderr.write('\n'.join(lines))
    self.stderr.write('\n')

  def get_server_proxy(self, namespace=None):
    proxy = self.options.getServerProxy()
    if namespace is None:
      return proxy
    return getattr(proxy,namespace)

  def get_restarter(self):
    return self.get_server_proxy('restarter')

  def upcheck(self):
    try:
      supervisor = self.get_server_proxy('supervisor')
      api = supervisor.getVersion() # deprecated
      from supervisor import rpcinterface
      if api != rpcinterface.API_VERSION:
        self.output(
            'Sorry, this version of supervisorctl expects to '
            'talk to a server with API version %s, but the '
            'remote version is %s.' % (rpcinterface.API_VERSION, api))
        return False
    except xmlrpclib.Fault, e:
      if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
        self.output(
            'Sorry, supervisord responded but did not recognize '
            'the supervisor namespace commands that supervisorctl '
            'uses to control it.  Please check that the '
            '[rpcinterface:supervisor] section is enabled in the '
            'configuration file (see sample.conf).')
        return False
      raise 
    except socket.error, why:
      if why[0] == errno.ECONNREFUSED:
        self.output('%s refused connection' % self.options.serverurl)
        return False
      elif why[0] == errno.ENOENT:
        self.output('%s no such file' % self.options.serverurl)
        return False
      raise
    return True

def send_restart(group,restarter=None,options=None,ctl=None):
  try:
    result = restarter.restartProcessGroup(group)
  except xmlrpclib.Fault, e:
    ctl.output_error('%s: ERROR (%s)' % (group,e.faultString))
    sys.exit(2)
  except socket.error, e:
    if e[0] == errno.ECONNREFUSED:
      ctl.output_error('%s: refused connection' % options.serverurl)
    elif e[0] == errno.ENOENT:
      ctl.output_error('%s: no such file' % options.serverurl)
    else:
      raise
    sys.exit(1)
  else:
    return result

def main(args=None,options=None):
  if options is None:
    options = ClientOptions()
  options.realize(args,doc=__doc__)
  ctl = Controller(options)
  if len(options.args) != 1:
    ctl.output_error('Invalid number of arguments (expected 1, got %d)' % len(options.args))
    sys.exit(5)
  ctl.upcheck()

  group = options.args[0].strip()
  restarter = ctl.get_restarter()
  result = None

  while 1:
    try:
      result = send_restart(group,options=options,ctl=ctl,restarter=restarter)
    except xmlrpclib.ProtocolError,e:
      if e.errcode == 401:
        if options.interactive:
          from getpass import getpass
          ctl.output('Server requires authentication')
          username = raw_input('Username:')
          password = getpass(prompt='Password:')
          ctl.output('')
          options.username = username
          options.password = password
          continue
        else:
          options.usage('Server requires authentication')
      else:
        ctl.output_error('%s: protocol error (%s)' % (group,e))
        sys.exit(10)
    break

  if result:
    if isinstance(result,(list,tuple)):
      for e in result:
        ctl.output_error('ERROR (%s)' % e['text'])
      sys.exit(len(result))
    ctl.output('%s: restarted' % group)
  else:
    ctl.output('%s: unknown state, server did not send a response' % group)

if __name__ == '__main__':
  main(sys.argv[1:])