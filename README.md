# p4pex
Servers and clients for EPICS PVAccess infrastructure.

Dependencies: ```pip install p4p```.

# simscope: p4p-based softIocPVA of a simulated oscilloscope
Similar to softIoc asyn/testAsynPortDriverApp

Usage:<br>
Grab the project from github an start the softIocPVA as:

    python -m p4pex.simscope -l

From another terminal:

    python -m p4p.client.cli get simScope1:WaveForm_RBV
    python -m p4p.client.cli put simScope1:NoiseAmplitude=10
    python -m p4p.client.cli get simScope1:WaveForm_RBV

