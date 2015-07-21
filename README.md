# RiSCHER: the RICH scheduler

_RiSCHER_ schedules timeslots and channels to all nodes of a Low-power Lossy Network. It is a centralized entity sitting outside the network and communicates with every node through the border router (LBR).

Besides the scheduling functionality, _RiSCHER_ can stream all the configuration/statistics coming from the network into a graph stream visualization server (e.g. Gephi). The schema below illustrates these components:
This is an optional functionality.

## Installation

The installation is split into two parts: (a) setting up the python environment for the scheduler, and (b) the visualization tool

###Scheduler setup and configuration

<ol>
<li>Install python 2.7.8 (python 3 is not supported)</li>
<li> Make sure the python executable is included in your environment path</li>
<li>Install the python module manager "pip". You may follow the guidelines of <a href="http://pip.readthedocs.org/en/latest/installing.html">this</a>. If clicking on "get-pip.py" displays the contents instead of downloading the file, you may right-click and save it. I trust terminal users can do something similar with e.g. _wget_.</li>
<li>In your terminal run the following commands:
<ol>
<li>python /path/to/downloaded/get-pip.py</li>
<li>pip install Twisted</li>
<li>pip install netaddr</li>
<li>pip install networkx</li>
<li>pip install txThings</li>
<li>pip install bitstring</li>
</ol>
</ol>
The are done with the environment for the scheduler!

###Visualizer

For visualization of the graph and statistics streamed from the scheduler, you may use Gephi.

<ol>
<li>Make sure you have the java build 1.7. Java build 1.8 is not supported </li>
<li>Download the Gephi version 0.8.2-beta from <a href="http://gephi.github.io/users/download/">here</a> </li>
<li>Install and run Gephi</li>
<li>In Gephi, go to Tools>Plugins>Available Plugins and select (tick) the Graph Streaming plugin. </li>
</ol>

## Usage

<ol>
<li>git pull scheduler repository to any location you prefer</li>
<li>Make sure the LBR is up and running. Note down the IPv6 address of the LBR e.g. aaaa::212:7401:1:101</li>
<li>If visualizer is needed:</li>
<ol>
<li>Double click on the richnet.gephi file. This is a configuration file of the visualizer with predefined graph attributes.</li>
<li>On the left tools panel>Streaming tab, right click the Master Server and select Start.</li>
<li>To change the port of the graph streaming server, select settings of the Streaming tab and adjust it (defaults to 8081)</li>
</ol>
<li>Open your terminal and 'cd' to the path of your scheduler repository</li>
<li>Run the scheduler with the following command: python rischer.py -b <IPv6 address of LBR> -v <IPv4:port of visualizer> <br/>
python rischer.py -h <br/>
python rischer.py -b aaaa::212:7401:1:101 -v 127.0.0.1:8081</li>
</ol>
