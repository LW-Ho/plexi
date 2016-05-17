## __plexi__: IEEE802.15.4e-TSCH network management entity

Exarchakos, G., Oztelcan, I., Sarakiotis, D., Liotta, A. "plexi: Adaptive re-scheduling web service of time synchronized low-power wireless networks", 2016, JNCA, Elsevier [in press]  - [cfp](http://www.journals.elsevier.com/journal-of-network-and-computer-applications/call-for-papers/special-issue-on-engineering-future-interoperable-and-open-i) - [preprint](https://george.autonomic-networks.ele.tue.nl/files/plexi.jnca.elsevier.camera.pdf)
***
_plexi_ is a restful web service API for monitoring and scheduling IEEE802.15.4e network resources hiding the complexity of schedule deployment and modification. The aim of the project is to enable applications configure and trigger at runtime new schedules of data transmissions after monitoring the network's performance. Re-scheduling TSCH networks to fulfill the expectations of one or more applications implies the network resources are continuously monitored and communication links created, moved, deleted over time.

For interoperability and scheduling purposes, _plexi_ exposes TSCH network resources e.g. communication channels and timeslots via a restful web interface for low power devices known as CoAP. For monitoring, _plexi_ captures the L2 and L3 network topology as well as the L2 schedule configuration and the performance metrics per link per node such as the number of retransmissions, packet delivery ratio, link quality indicator and received signal strength. _plexi_ consists of two parts:

* **network management entity**: NME is an API provided to either external schedulers or applications - [source code](https://github.com/gexarchakos/plexi) - [api docs](https://george.autonomic-networks.ele.tue.nl/api/plexi/nme") - [tutorials](#)
* **device plexi interface**: device CoAP interface to monitor the links and modify their schedule -  [source code](https://github.com/gexarchakos/contiki/tree/plexi/apps/plexi) - [api docs](https://george.autonomic-networks.ele.tue.nl/api/plexi/node/contiki) - [example](https://github.com/gexarchakos/contiki/tree/plexi/examples/plexi-rpl-tsch)

### installation

1. Make sure you have Python 2.7 (>2.7.6 preferred) installed. Python 3 is not supported. In your local terminal (e.g. bash) run: ```python --version``` to confirm the version of your python.
2. Make sure you have ```pip``` installed. If not, follow these [instructions](https://pip.pypa.io/en/stable/installing/).
3. Install the following libraries with ```pip```:
```Bash
$ pip install setuptools
$ pip install Twisted
$ pip install netaddr
$ pip install networkx
$ pip install txThings
$ pip install bitstring
$ pip install ipaddress
```

### usage

___plexi nme___ is the centralized counterpart of ___plexi interface___ available at every node. ___plexi interface___ executes commands sent by ___plexi nme___ and is, currently, available only in Contiki 3.0 [here](https://github.com/gexarchakos/contiki/tree/plexi/apps/plexi). Some instructions on how to work with both you may find [here](https://george.autonomic-networks.ele.tue.nl/work-with-gitlab-repo/).

Assuming a working RPL border router (LBR) accessible over IPv6 from the host of _plexi nme_, below the steps to use it:
* Note down the IPv6 address of the LBR e.g. ```aaaa::c30c:0:0:1```
<li>Open your terminal and 'cd' to the path of your scheduler repository</li>
<li>Run the scheduler with the following command: python rischer.py -b <IPv6 address of LBR> -v <IPv4:port of visualizer> <br/>
python rischer.py -h <br/>
python rischer.py -b aaaa::212:7401:1:101 -v 127.0.0.1:8081</li>
</ol>
