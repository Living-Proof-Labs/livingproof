Command reference
=================

Generated from the installed candidate wheel's Click definitions. The root-only
reference deliberately lists optional capability names without importing a plugin.
The terminal help below is captured from fresh installed container images.
No command list or option descriptions are maintained by hand.

Root command
------------

.. click:: livingproof.cli:main
   :prog: livingproof

Capability discovery
--------------------

.. click:: livingproof.cli:capability
   :prog: livingproof capability

Plugin management
-----------------

.. click:: livingproof.plugin_management:plugins
   :prog: livingproof plugins
   :nested: full

Completion
----------

.. click:: livingproof.completion:completion
   :prog: livingproof completion
   :nested: full

Installed terminal help
-----------------------

.. include:: generated-help.rst
