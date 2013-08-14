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

from ConfigParser import NoOptionError,NoSectionError,ParsingError
from ConfigParser import Error as ConfigParserError
from time import time
import pkg_resources
pkg_resources.require('supervisor >= 3.0a')

from supervisor import xmlrpc
from supervisor.xmlrpc import Faults
from supervisor.states import RUNNING_STATES,STOPPED_STATES,\
                              ProcessStates,SupervisorStates,\
                              getProcessStateDescription
from supervisor.options import UnhosedConfigParser
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

_marker = object()
class ConfigParser(UnhosedConfigParser):
  mysection = 'rpcinterface:restarter'

  def getint(self,option,default=_marker):
    try:
      return UnhosedConfigParser.getint(self,self.mysection,option)
    except NoOptionError:
      if default is _marker:
        raise
      return default

  def getfloat(self,option,default=_marker):
    try:
      return UnhosedConfigParser.getfloat(self,self.mysection,option)
    except NoOptionError:
      if default is _marker:
        raise
      return default

  def getboolean(self,option,default=_marker):
    try:
      return UnhosedConfigParser.getboolean(self,self.mysection,option)
    except NoOptionError:
      if default is _marker:
        raise
      return default

  def items(self):
    return UnhosedConfigParser.items(self,self.mysection)

  def has_section(self,section=None):
    if section is None:
      section = self.mysection
    return UnhosedConfigParser.has_section(self,section)

  def read(self,filenames):
    if isinstance(filenames,basestring):
      filenames = (filenames,)
    if filenames and not sum(1 for fn in filenames if os.path.isfile(fn)):
      raise ParsingError, 'no config files found'
    return UnhosedConfigParser.read(self,filenames)

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
  default_config = {'delay': 0.2,
                    'timeout': 5.0,
                    'stagger_factor': 1}

  def __init__(self, supervisord, config):
    self.supervisord = supervisord
    self._version = None
    self._config(config.items())
    super(RPCInterface,self).__init__()

  def _get_config(self):
    return dict((k,getattr(self,k)) for k in self.default_config.keys())

  def _config(self,items):
    cdict = self.default_config.copy()
    for k,v in items:
      if k in cdict:
        setattr(self,k,type(cdict[k])(v))

    for k,v in self.default_config.items():
      if k not in self.__dict__:
        setattr(self,k,v)

  def _update(self,text):
    self.update_text = text
    if self.supervisord.options.mood < SupervisorStates.RUNNING:
      raise RPCError(Faults.SHUTDOWN_STATE)

  def reconfigureFrom(self,data):
    '''Reconfigure the plugin from a hash containing configurtion key,value pairs.

    @param struct data        a hash of key,value pairs
    @returns struct config    a hash of current configuration options (after update)
    '''
    if not isinstance(data,dict):
      raise RPCError(Faults.INCORRECT_PARAMETERS)

    updates = dict()
    for k,v in data.items():
      try:
        updates[k] = type(self.default_config[k])(v)
      except KeyError:
        raise RPCError(Faults.BAD_ARGUMENTS,'%r is not a valid configuration option' % k)
      except ValueError:
        raise RPCError(Faults.BAD_ARGUMENTS,'%r does not have the correct value type' % k)

    if updates:
      self._config(updates.items())
    return self._get_config()

  def reconfigure(self,*filenames):
    '''Reconfigure the plugin from one or more config files. If no filenames
are passed, returns a hash of the current configuration.

    @return struct config  a hash of current configuration options (after update)
    '''
    if filenames:
      parser = ConfigParser(defaults=dict((k,str(v)) for k,v in self.default_config.items()))
      try:
        parser.read(filenames)
      except ConfigParserError, e:
        raise RPCError(Faults.FAILED,str(e))
      if not parser.has_section():
        raise RPCError(Faults.FAILED,'config file(s) has no [%s] section.' % parser.mysection)
      self._config(parser.items())
    return self._get_config()

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
      # stagger_factor is how "often" we stop procs
      # 2 = every other call
      # 3 = every third call, etc
      stagger = min(self.stagger_factor or 1,len(unstopped) or 1)
      stop_modulus = loop_count % stagger
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
                        '%s: bad state during start [%s]' % (name,_get_state_desc(state))))
            ignore.add(name)

      for i,name in enumerate(sorted(unstopped,reverse=True)):
        if loop_count < stagger and (i % stagger) != stop_modulus:
          continue
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
  return RPCInterface(supervisord,config)
