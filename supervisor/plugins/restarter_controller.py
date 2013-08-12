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

import sys,xmlrpclib,pkg_resources

pkg_resources.require(['supervisor >= 3.0a',
                       'supervisor-restarter >= 1.0.2'])
from supervisor.supervisorctl import ControllerPluginBase
from supervisor.plugins.restarter import RestarterFaults

class RestarterControllerPlugin(ControllerPluginBase):
  '''restart_group <group-name>

Restart a process group by name.
  '''
  name = 'restarter'

  def do_restart_group(self, arg):
    if not self.ctl.upcheck():
      return

    output = self.ctl.output
    args = arg.strip().split()
    if len(args) < 1:
      output('Error: too few arguments')
      return
    elif len(args) > 1:
      output('Error: too many arguments')
      return

    group = args[0]
    restarter = self.ctl.get_server_proxy(self.name)
    result = None
    interactive = self.ctl.options.interactive

    try:
      result = restarter.restartProcessGroup(group)
    except xmlrpclib.Fault, e:
      if e.faultCode == RestarterFaults.BAD_GROUP:
        output('%r is not a valid process group on this server' % group)
        if not interactive:
          sys.exit(1)
        return
      elif e.faultCode in RestarterFaults._codes:
        output('restarter error: %s' % e.faultString)
        if not interactive:
          sys.exit(1)
        return
      elif e.faultString:
        output(e.faultString)
        if not interactive:
          sys.exit(1)
        return
      else:
        raise

    if result:
      if isinstance(result,(list,tuple)):
        for i,e in enumerate(result):
          output("ERROR %d (%s)" % (i,e['text']))
        if not interactive:
          sys.exit(len(result))
      elif isinstance(result,basestring):
        output('%s restarted (%s)' % (group,result))
      else:
        output('%s restarted' % group)
    else:
      output('%s: unknown state, server did not sense a response' % group)
      if not interactive:
        sys.exit(1)

# vi: :set sts=2 sw=2 ai et tw=0:
