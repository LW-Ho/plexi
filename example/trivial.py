__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.12"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from example import main
from core.schedule import Scheduler, logg
from core.slotframe import Slotframe
from util import terms
import sys


class TrivialScheduler(Scheduler):
	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer):
		super(TrivialScheduler, self).__init__(net_name, lbr_ip, lbr_port, prefix, visualizer)

	def start(self):
		self.communicate(self.get_remote_children(self.root_id))
		f1 = Slotframe("Broadcast-Frame", 25)
		self.frames[f1.name] = f1
		q = self.set_remote_frames(self.root_id, f1)
		q.append(self.set_remote_link(1, 0, f1, self.root_id, None, self.root_id))
		self.communicate(q)

		f2 = Slotframe("Unicast-Frame", 21)
		self.frames[f2.name] = f2
		self.communicate(self.set_remote_frames(self.root_id, f2))
		super(TrivialScheduler, self).start()

	def connected(self, child, parent, old_parent=None):

		commands = [self.get_remote_children(child, True)]

		#TODO commands.append(self.Command('post', child, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"})) # First step of statistics installation.

		bcq = self.set_remote_frames(child, self.frames["Broadcast-Frame"])
		for c in self.frames["Broadcast-Frame"].cell_container:
			if c.tx_node == parent or c.tx_node in self.dodag.get_children(child):
				bcq.append(self.set_remote_link(c.slot, c.channel, self.frames["Broadcast-Frame"], c.tx_node, None, child))
		bso, bco = self.schedule(child, None, self.frames["Broadcast-Frame"])
		if bso and bco:
			bcq.append(self.set_remote_link(bso, bco, self.frames["Broadcast-Frame"], child, None))
		else:
			logg.critical("INSUFFICIENT BROADCAST SLOTS: new node " + str(child) + " cannot broadcast")
		commands.append(bcq)

		ucq = self.set_remote_frames(child, self.frames["Unicast-Frame"])
		for neighbor in [parent]+self.dodag.get_children(child):
			uso, uco = self.schedule(neighbor, child, self.frames["Unicast-Frame"])
			if uso and uco:
				ucq.append(self.set_remote_link(uso, uco, self.frames["Unicast-Frame"], neighbor, child))
			else:
				logg.critical("INSUFFICIENT UNICAST SLOTS: new node " + str(child) + " cannot receive from " + str(neighbor))
			uso, uco = self.schedule(child, neighbor, self.frames["Unicast-Frame"])
			if uso and uco:
				ucq.append(self.set_remote_link(uso, uco, self.frames["Unicast-Frame"], child, neighbor))
			else:
				logg.critical("INSUFFICIENT UNICAST SLOTS: new node " + str(child) + " cannot unicast to " + str(neighbor))
		commands.append(ucq)
		return commands

	def schedule(self, tx, rx, slotframe):
		max_slots = 0
		for frame in self.frames:
			if max_slots < frame.slots:
				max_slots = frame.slots
		so = None
		co = None
		for slot in range(1, max_slots):
			skip = False
			free_channels = set(range(16))
			for frame in self.frames:
				free_channels = free_channels.difference(self.interfere(slot, tx, rx, frame))
				if len(free_channels) == 0 or self.conflict(slot, tx, rx, frame):
					skip = True
					break
			if not skip:
				so = slot
				co = free_channels[0]
				break

		return so,co

	def probed(self, node_id, metric_id):
		logg.info(str(node_id) + " installed statistics observer with id=" + str(metric_id))
		commands = []

		id_appended_uri = terms.uri['6TP_SV'] + "/" + str(metric_id)
		commands.append(self.Command('observe', node_id, id_appended_uri))

		return commands

	def reported(self, node_id, endpoint, statistics):
		if node_id in statistics:
			logg.info(str(node_id) + " for " + str(endpoint) + " reported >> " + str(statistics[node_id]))


if __name__ == '__main__':
	x = main.get_user_input(None)
	if isinstance(x, main.UserInput):
		sch = TrivialScheduler(x.network_name, x.lbr, x.port, x.prefix, x.visualizer)
		sch.start()
		sys.exit(0)
	sys.exit(x)