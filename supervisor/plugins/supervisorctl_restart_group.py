# Copyright [2013] Jesse Sipprell <jessesipprell@gmail.com>
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

def main(args=None,options=None):
  if options is None:
    options = ClientOptions()
  options.realize(args,doc=__doc__)
  if not options.args or len(options.args) != 1:
    print >>sys.stderr,'Invalid number of arguments (expected 1, got %d)' % len(args)
  group = options.args[0].strip()
  server = xmlrpclib.Server(options.serverurl)

  try:
    result = server.restarter.restartProcessGroup(group)
  except xmlrpclib.Fault, e:
    print >>sys.stderr,'%s: ERROR (%s)' % (group,e.faultString)
    sys.exit(2)
  except socket.error, e:
    if e[0] == errno.ECONNREFUSED:
      print >>sys.stderr,'%s: refused connection' % options.serverurl
    elif e[0] == errno.ENOENT:
      print >>sys.stderr,'%s: no such file' % options.serverurl
    else:
      raise
    sys.exit(1)
  else:
    if isinstance(result,(list,tuple)):
      for e in result:
        print >>sys.stderr,'%s: ERROR (%s)' % (group,e.faultString)
      sys.exit(len(result))

    print '%s: restarted' % group

if __name__ == '__main__':
  main(sys.argv[1:])