supervisor-restarter
====================

Plugin package for supervisor that can perform fast restarts of supervisor process groups via an xmlrpc call


#### The Problem

Due to inherent architecture design python-supervisor waits (currently, unpactched) one second after restarting
a process. While this can be patched to a lower time value it represents a scalability issue given sufficient
processes in a process group.

supervisor-restarter provides an xmlrpc call which can rapidly restart a process group by adding a new module
to the `supervisor.plugins` namespace. Note that while `supervisor` is already a _namespace_, `plugins` will
be added as such via the setuptools `pkg_resources` mechanism.

supervisor-restarter should be compatible with Python 2.4 through 2.7. It is untested (and probably incompatible)
with Python 3 and higher.

#### Configuration

To configure the restarter XML RPC interface you will need a main config section or drop file for supervisor
containing the following:

    [rpcinterface:restarter]
    supervisor.rpcinterface_factory = supervisor.plugins.restarter:make_rpcinterface
    ;delay = 0.1
    ;timeout = 5.0

The **delay** option can be used to configure the delay, in seconds, between internal "callback" iterations of
the `restartProcessGroup` rpc call. *A default of 0.2 seconds is used if none is otherwise configured.*

The **timeout** option will configure the maximum amount of time, in seconds, that the xmlrpc method `restartProcessGroup`
will be allowed to run; although "run" is slightly deceptive because, as indicated above, the underlying method is actually
non-blocking and is called every **delay** seconds until it indicates the operation is complete. **timeout** simply bounds
this to a maximum time. Once this time limit has been reached the xmlrpc call will return a Fault or a list containing
faults (as dictionaries) if prior errors have accumulated. The timeout is not exact as it can only be checked every
**delay** seconds. *A default timeout of 5 seconds is used if not otherwise configured.*

#### Usage
    
    $ python
    Python 2.7.1 (...)
    >>> import xmlrpclib
    >>> server = xmlrpclib.Server('http://localhost:9001/RPC2')
    >>> server.restarter.restartProcessGroup('someconfiguredgroup')
    True

## Client Script

Eventually the plan is to extend `supervisorctl` in a similar fashion. However, for the moment, it's not possible to
extend the ctl interface via a _supervisor.d/_ *.conf file, only by editing the main config. Thus, the following tool is
now included in this package:

#### supervisorctl_restart_group

Restarts the process group passed on the command line. Takes all the same arguments as `supervisorctl`.

Example:

    supervisorctl_restart_group -s http://myserver foobar
    
Restarts the foobar process group on _myserver_.
