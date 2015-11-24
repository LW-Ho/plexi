__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.12"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from example import main
from core.schedule import SchedulerInterface, logg
from core.slotframe import Slotframe
from core.interface import BlockQueue, Command
from util import terms
import sys
from twisted.internet import task
from core.node import NodeID

class Monitor(SchedulerInterface):
	"""
	Usage example of RiSCHER API v0.4. Each node is scheduled and assigned with:

	- two :class:`core.slotframe.Slotframe`. One slotframe for Broadcast :class:`core.slotframe.Cell` of length 25 slots and another slotframe for Unicast :class:`core.slotframe.Cell` of length 21 slots.
	- one broadcast cell and one unicast cell
	- one observer for the children list
	- one observer for PRR and RSSI statistics

	Nodes are allocated cells starting from channel 0 and slot 1. Priority is given to fill in the channels before another
	slot is used. Given an intended link between two nodes, the :class:`TrivialScheduler` checks all channels of a slot to
	find possible conflicts or interferences with other transmissions. If none of the two, the link is allocated a cell on
	that slot, if available. Otherwise, the next slot is checked.
	"""

	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer=None):
		super(Monitor,self).__init__(net_name, lbr_ip, lbr_port, prefix, visualizer)
		self.observeflag = True
		mainstream_frame = Slotframe("broadcast", 25)
		self.frames[mainstream_frame.name] = mainstream_frame
		self._register_frames([mainstream_frame])
		self.Streamer.DumpDotData()
		#dictionary is build as:
		#key: ip of node
		#value: dict with
		#	key: ip of target
		#	value: number of packets in queue
		self.qstats = {}

	def RequestAllQueues(self):
		#TODO: ask all queues at once instead of the block
		logg.debug("Requesting all queues")
		for node in self.dodag.graph.nodes():
			self.communicate(self.get_remote_queues(node))


	def start(self):
		# self.l = task.LoopingCall(self.RequestAllQueues)
		# self.l.start(30)
	# 	# ALWAYS include this at the end of a scheduler's start() method
	# 	# The twisted.reactor should be run after there is at least one message to be sent
	 	super(Monitor, self).start()

	def reported(self, node, resource, value):
		if str(resource).startswith(terms.get_resource_uri('6TOP', 'QUEUELIST')):
			# logg.debug("Received list:{}".format(value))
			change = False
			if str(node) not in self.qstats:
				self.qstats[str(node)] = {}

			for k,v in value.iteritems():
				if k.split(":")[0] != "215":
					continue
				if str(node) == str(self.dodag.get_parent(self.dodag.get_node(v))):
					continue
				target = NodeID(k)
				if str(target) not in self.qstats[str(node)]:
					self.qstats[str(node)][str(target)] = "QueueLength:{}".format(v)
					logg.info("Node {} reported: Queue {}: length: {}".format(node,k,v))
					change = True
				else:
					if self.qstats[str(node)][str(target)] != "QueueLength:{}".format(v):
						change = True
						self.qstats[str(node)][str(target)] = "QueueLength:{}".format(v)
						logg.info("Node {} reported: Queue {}: length: {}".format(node,k,v))
					else:
						logg.debug("Node {} reported: Queue {}: length: {}".format(node,k,v))
			if change:
				self.Streamer.DumpDotData(labels=self.qstats)

if __name__ == '__main__':
	x = main.get_user_input(None)
	if isinstance(x, main.UserInput):
		v = {
			"name"	:	"plexi1",
			"Key"	:	None,
			"VHost"	:	"localhost"
		}
		sch = Monitor(x.network_name, x.lbr, x.port, x.prefix, v)
		sch.start()
		sys.exit(0)
	sys.exit(x)
