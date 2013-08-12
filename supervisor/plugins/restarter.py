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

from time import time
import pkg_resources
pkg_resources.require('supervisor >= 3.0a')

from supervisor import xmlrpc
from supervisor.xmlrpc import Faults
from supervisor.states import RUNNING_STATES,STOPPED_STATES,\
                              ProcessStates,SupervisorStates,\
                              getProcessStateDescription
from supervisor.http import NOT_DONE_YET
from weakref import WeakValueDictionary

API_VERSION = '3.0'
STARTING = ProcessStates.STARTING
STOPPING = ProcessStates.STOPPING
BACKOFF = ProcessStates.BACKOFF

def _get_state_desc(state):
  desc = getProcessStateDescription(state)
  if desc:
    return desc
  return str(state)

class Timer(object):
  __slots__ = ('start_time','_counter')

  def __init__(self,start=False,start_counter=0):
    super(Timer,self).__init__()
    self.start_time = -1
    self._counter = start_counter-1
    if start:
      self.start()

  def start(self):
    if self.start_time >= 0:
      raise ValueError, 'timer already started'
    self.start_time = time()

  def is_started(self):
    return self.start_time >= 0

  def elapsed(self):
    if self.start_time < 0:
      raise ValueError, 'timer is not stated'
    return time() - self.start_time

  def inc_counter(self,value=1):
    self._counter += value
    return self._counter

class RestarterFaults(object):
  BAD_GROUP = 0x400
  BAD_STATE = 0x410
  TIMEOUT = 0x420
  START_FAILED = 0x430
  STOP_FAILED = 0x431

RestarterFaults._codes = dict((getattr(RestarterFaults,a),a)
                              for a in dir(RestarterFaults) if a.isupper())

class RPCError(xmlrpc.RPCError):
  def __init__(self,code,extra=None):
    if code in RestarterFaults._codes:
      text = RestarterFaults._codes[code]
      self.code = code
      if extra:
        self.text = '%s: %s' % (text,extra)
      else:
        self.text = text
    else:
      RPCError.__init__(self,code,extra)

class RPCInterface(object):
  def __init__(self, supervisord, delay, timeout):
    self.supervisord = supervisord
    self.delay = delay
    self.timeout = timeout
    self._version = None
    super(RPCInterface,self).__init__()

  def _update(self,text):
    self.update_text = text
    if self.supervisord.options.mood < SupervisorStates.RUNNING:
      raise RPCError(Faults.SHUTDOWN_STATE)

  def getPluginVersion(self):
    '''Return the plugin version that provides rpc methods for this namespace.

    @return string version version id
    '''
    from os.path import join

    self._update('getPluginVersion')
    if self._version is None:
      version_txt = join(here,'%s_version.txt' % (__name__.split('.')[-1],))
      try:
        f = open(version_txt,'r')
        try:
          self._version = f.read()
        finally:
          f.close()
      except IOError,e:
        raise RPCError(Faults.FAILED,str(e))
    return self._version

  def getAPIVersion(self):
    '''Return the version of the RPC API used by this supervisord plugin.

    @return string version version id
    '''
    self._update('getAPIVersion')
    return API_VERSION

  def restartProcessGroup(self, name):
    '''Restart all procs in supervisor process group .. rapidly!
    Returns a list of rpc faults if an error occurs.

    @param string name          name of process group to restart
    @return boolean result      true if successful
    '''
    self._update('restartProcessGroup')
    group = self.supervisord.process_groups.get(name)
    if group is None:
      raise RPCError(RestarterFaults.BAD_GROUP)

    transit_states = (STARTING,STOPPING)
    processes = WeakValueDictionary((p.config.name,p) for p in group.processes.itervalues())
    allprocs = set(processes.keys())
    procnames = [p.config.name for p in group.get_unstopped_processes()]
    unstopped = set(procnames)
    started = set()
    ignore = set()
    errs = list()
    timer = Timer()

    def get_proc(name):
      try:
        return processes[name]
      except KeyError:
        if name in procnames:
          procnames.remove(name)
        unstopped.discard(name)
        started.discard(name)
        ignore.discard(name)

    def restartem():
      loop_count = timer.inc_counter()
      if not timer.is_started():
        timer.start()
      elif timer.elapsed() > self.timeout:
        nremaining = (len(allprocs) - len(started.union(ignore))) + len(unstopped)
        e = RPCError(RestarterFaults.TIMEOUT,
          'timeout expired after %.1f seconds, loop count %d, %d procs pending restart' % \
          (timer.elapsed(),loop_count,nremaining))
        if errs:
          errs.append(e)
          return errs
        raise e
      for name in sorted(allprocs):
        p = get_proc(name)
        if p is None:
          continue
        if name not in unstopped and name not in started and name not in ignore:
          state = p.get_state()
          if state == BACKOFF:
            if loop_count > 0:
              errs.append(RPCError(RestarterFaults.START_FAILED,
                          '%s: process failing startup, in backoff mode' % (name,)))
              ignore.add(name)
            else:
              msg = p.stop()
              if msg is not None:
                errs.append(RPCError(RestarterFaults.STOP_FAILED,'BACKOFF/%s: %s' % (name,msg)))
                ignore.add(name)
          elif state != STARTING and state in RUNNING_STATES:
            started.add(name)
          elif state in STOPPED_STATES:
            p.spawn()
            if p.spawnerr:
              errs.append(RPCError(Faults.SPAWN_ERROR,name))
              ignore.add(name)
          elif state not in transit_states:
            errs.append(RPCError(RestarterFaults.BAD_STATE,
                        '%s: bad state during start [%s]' % (name,_get_state_desc(state)))
            ignore.add(name)

      for name in sorted(unstopped,reverse=True):
        p = get_proc(name)
        if p is None:
          continue
        state = p.get_state()
        unstopped.discard(name)
        if state in RUNNING_STATES:
          msg = p.stop()
          if msg is not None:
            errs.append(RPCError(RestarterFaults.STOP_FAILED,'%s: %s' % (name,msg)))
            ignore.add(name)
        elif state not in STOPPED_STATES and state not in transit_states:
          errs.append(RPCError(Faults.BAD_STATE,
                      '%s: bad state during stop [%s]' % (name,_get_state_desc(state))))
          ignore.add(name)

      if not unstopped and started.union(ignore) == allprocs:
        if errs:
          return errs
        return True
      return NOT_DONE_YET
 
    restartem.delay = self.delay
    restartem.rpcinterface = self
    return restartem
        
def make_rpcinterface(supervisord,**config):  
  return RPCInterface(supervisord,delay=float(config.get('delay',0.2)),
                                  timeout=float(config.get('timeout',5.0)))
