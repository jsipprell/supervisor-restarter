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

import pkg_resources
pkg_resources.require('supervisor >= 3.0a')

from supervisor.xmlrpc import Faults,RPCError
from supervisor.states import RUNNING_STATES,STOPPED_STATES
from supervisor.http import NOT_DONE_YET

class RPCInterface(object):
  def __init__(self, supervisord, delay):
    self.supervisord = supervisord
    self.delay = delay
    super(RPCInterface,self).__init__()

  def restartProcessGroup(self, name):
    '''Restart all procs in supervisor process group .. rapidly!
    Returns a list of rpc faults if an error occurs.

    @param string name          name of process group to restart
    @return boolean result       true if successful
    '''

    group = self.supervisord.process_groups.get(name)
    if group is None:
      raise RPCError(Faults.BAD_NAME)

    processes = dict([(p.config.name,p) for p in group.get_unstopped_processes()])
    procnames = processes.keys()
    unstopped = set(procnames)
    started = set()
    ignore = set()
    errs = list()
    
    def restartem():
      for name in sorted(procnames):
        p = processes[name]
        if name not in unstopped and name not in started and name not in ignore:
          state = p.get_state()
          if state in RUNNING_STATES:
            errs.append(RPCError(Faults.FAILED,'%s: already running' % (name,)))
            ignore.add(name)
          elif state in STOPPED_STATES:
            p.spawn()
            if p.spawnerr:
              errs.append(RPCError(Faults.SPAWN_ERROR,name))
              ignore.add(name)
            else:
              started.add(name)
          else:
            ignore.add(name)

      for name in sorted(unstopped):
        p = processes[name]
        state = p.get_state()
        unstopped.remove(name)
        if state in RUNNING_STATES:
          msg = p.stop()
          if msg is not None:
            errs.append(RPCError(Faults.FAILED,'%s: %s' % (name,msg)))
            ignore.add(name)
        elif state not in STOPPED_STATES:
          ignore.add(name)

      if not unstopped and started.union(ignore) == set(procnames):
        if errs:
          return errs
        return True
      return NOT_DONE_YET
 
    restartem.delay = self.delay
    restartem.rpcinterface = self
    return restartem
        
def make_rpcinterface(supervisord,**config):  
  return RPCInterface(supervisord,float(config.get('delay',0.2)))
