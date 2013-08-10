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

To configure the restarter XML RPC interface you will need a config snipped or drop file for supervisor containing the following:

    [rpcinterface:restarter]
    supervisor.rpcinterface_factory = supervisor.plugins.restarter:make_rpcinterface
    ;delay = 0.1
    
The **delay** option can be used to configure the delay, in seconds, between internal "callback" iterations of
the `restartProcessGroup` rpc call. *A default of 0.2 seconds is used if none is otherwise configured.*

#### Usage
    
    $ python
    Python 2.7.1 (...)
    >>> import xmlrpclib
    >>> server = xmlrpclib.Server('http://localhost:9001/RPC2')
    >>> server.restarter.restartProcessGroup('someconfiguredgroup')
    True
