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

	def start(self):
		# ALWAYS include this at the end of a scheduler's start() method
		# The twisted.reactor should be run after there is at least one message to be sent
		super(Monitor, self).start()


if __name__ == '__main__':
	x = main.get_user_input(None)
	if isinstance(x, main.UserInput):
		sch = Monitor(x.network_name, x.lbr, x.port, x.prefix, False)
		sch.start()
		sys.exit(0)
	sys.exit(x)