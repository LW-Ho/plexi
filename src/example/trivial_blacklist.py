__author__ = "George Exarchakos, Frank Boerman"
__email__ = "g.exarchakos@tue.nl, f.j.l.boerman@student.tue.nl"
__version__ = "0.0.12"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from example import main
from core.schedule import Scheduler, logg
from core.slotframe import Slotframe
from core.interface import BlockQueue, Command
from util import terms
import sys
from sets import Set
from twisted.internet import task
from twisted.internet import reactor

class TrivialScheduler(Scheduler):
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
		"""
		Configure root node and start the :class:`TrivialScheduler`. The root node will have:

		- a broadcast frame of 25 slots and one broadcast cell at channel 0 and slot 1
		- a unicast frame of 21 slots
		- an observer of the PRR and RSSI statistics

		:note: uses :func:`core.schedule.Reflector.start` to initiate communication with LBR
		"""

		# Define a frame of size 25 slots containing broadcast cells
		f1 = Slotframe("Broadcast-Frame", 16)
		# Register that frame to the dictionary of frames of the parent Reflector
		self.frames[f1.name] = f1
		# Produce a BlockQueue of commands which install the frame to root
		q = self.set_remote_frames(self.root_id, f1)
		# Once frame installed, install a broadcast cell to root on its broadcast frame
		q.push(self.set_remote_link(1, 0, f1, self.root_id, None, self.root_id))
		# Start sending the commands in q
		self.communicate(q)

		f2 = Slotframe("Unicast-Frame", 16)
		self.frames[f2.name] = f2
		self.communicate(self.set_remote_frames(self.root_id, f2))

		# Build and send a BlockQueue for a statistics observer
		self.communicate(self.set_remote_statistics(self.root_id, {"mt":"[\"PRR\",\"RSSI\",\"ETX\"]"}))
		self._register_frames([f1, f2])

		#the dictionary that holds all the statistics data
		self.statistics = {}
		#some blacklist settings
		#TODO: make these variable for: 1) usergui 2)relative to earlier values (running average?)
		self.PRR_Floor = 30
		self.ETX_Ceil = 800

		#which frame needs to altered when a parent rewire happens
		self.rewireframe = "Unicast-Frame"

		#setup a callback to start the statistics check delayed to give network time to start
		reactor.callLater(2.5*60,self.startStatCheck)

		# ALWAYS include this at the end of a scheduler's start() method
		# The twisted.reactor should be run after there is at least one message to be sent
		super(TrivialScheduler, self).start()

	def startStatCheck(self):
		self.statcheck = False
		# #setup a check for statistic check
		# self.l = task.LoopingCall(self.CheckStatistic)
		# #the ammount of seconds can be finetuned here
		# self.l.start(60)

	def connected(self, child, parent, old_parent=None):
		"""
		Configure newly connected node to communicate with neighbors. Configure both child and its neighbors as follows:

		- a broadcast frame of 25 slots and a unicast frame of 21 slots
		- a transmitting broadcast cell at child for the child's (Tx) broadcasting to its neighbors (Rx)
		- the receiving broadcast cells at the neighbors for child's broadcast
		- receiving only broadcast cells at child for neighbors' broadcasts
		- one transmit unicast cell at child for every unicast child->neighbor link
		- one receive unicast cell at a neighbor for every unicast child->neighbor link
		- one transmit unicast cell at neighbor for every unicast neighbor->child link
		- one receive unicast cell at child for every unicast neighbor->child link
		- an observer of the PRR and RSSI statistics

		:param child: the newly connected node
		:type child: NodeID
		:param parent: the current parent of child at the DoDAG
		:type parent: NodeID
		:param old_parent: the previous parent of child at the DoDAG (in case of rewiring)
		:type old_parent: NodeID or None -if not rewiring-
		:return: list of BlockQueues that handle the all concurrent transactions with the node and its neighbors
		"""

		# Make a list of BlockQueues that should be transmitted simultaneously
		commands = []

		# Define a BlockQueue for broadcast cells. Make sure to block() before cells are added to this BlockQueue
		bcq = self.set_remote_frames(child, self.frames["Broadcast-Frame"])

		# Scan through all broadcast cells to detect those that the child (new node) should listen to.
		# As soon as one is found, create a Tx cell and append it to the broadcast frame
		# Be careful. Avoid scanning through the cells you just create
		for c in self.frames["Broadcast-Frame"].cell_container:
			skip = False
			for new_command in bcq:
				if new_command.uri == terms.uri['6TP_CL'] and c.slot == new_command.payload['so'] and c.channel == new_command.payload['co'] and c.option == new_command.payload['lo'] and c.owner == new_command.to and c.type == new_command.payload['lt']:
					skip = True
			if skip:
				continue
			if c.tx == parent or c.tx in self.dodag.get_children(child):
				# Note that set_remote_link modifies the cell_container you are also reading in this loop
				bcq.push(self.set_remote_link(c.slot, c.channel, self.frames["Broadcast-Frame"], c.tx, None, child))

		# Schedule a broadcast cell for the child, if there is space in the Broadcast-Frame
		bso, bco = self.schedule(child, None, self.frames["Broadcast-Frame"])
		if bso is not None and bco is not None:
			bcq.push(self.set_remote_link(bso, bco, self.frames["Broadcast-Frame"], child, None))
		else:
			logg.critical("INSUFFICIENT BROADCAST SLOTS: new node " + str(child) + " cannot broadcast")
		bcq.block()

		commands.append(bcq)

		# Define another BlockQueue for unicast cells. Make sure to block() before cells are added to this BlockQueue
		ucq = self.set_remote_frames(child, self.frames["Unicast-Frame"])

		# Allocate one unicast cell per links with every neighbor of child
		for neighbor in [parent]+self.dodag.get_children(child):
			# schedule the neighbor->child link
			# uso, uco = self.schedule(neighbor, child, self.frames["Unicast-Frame"])
			# if uso is not None and uco is not None:
			# 	ucq.push(self.set_remote_link(uso, uco, self.frames["Unicast-Frame"], neighbor, child))
			# else:
			# 	logg.critical("INSUFFICIENT UNICAST SLOTS: new node " + str(child) + " cannot receive from " + str(neighbor))
			ucq = self.Schedule_Link(neighbor, child, self.frames["Unicast-Frame"], ucq)

			# schedule the child->neighbor link
			# uso, uco = self.schedule(child, neighbor, self.frames["Unicast-Frame"])
			# if uso is not None and uco is not None:
			# 	ucq.push(self.set_remote_link(uso, uco, self.frames["Unicast-Frame"], child, neighbor))
			# else:
			# 	logg.critical("INSUFFICIENT UNICAST SLOTS: new node " + str(child) + " cannot unicast to " + str(neighbor))
			ucq = self.Schedule_Link(child, neighbor, self.frames["Unicast-Frame"], ucq)
		ucq.block()
		commands.append(ucq)

		# Build and send a BlockQueue for a statistics observer
		commands.append(self.set_remote_statistics(child, {"mt":"[\"PRR\",\"RSSI\",\"ETX\"]"}))

		return commands

	def Schedule_Link(self, tx, rx, slotframe,q):
		uso, uco = self.schedule(tx, rx, slotframe)
		if uso is not None and uco is not None:
			q.push(self.set_remote_link(uso, uco, slotframe, tx, rx))
		else:
			logg.critical("INSUFFICIENT " + slotframe.name + " SLOTS: new node " + str(rx) + " cannot receive from " + str(tx))
		return q

	def schedule(self, tx, rx, slotframe):
		"""
		Schedules a link at a given slotframe.

		Starts from slot 1 and channel 0. All the channels of the slot are scanned. If the intended link does not conflict
		with any simultaneous transmission at that slot and does not interfere with any other pair of nodes, the link is
		scheduled at that channel and slot. If no such channel can be found, the next slot is scanned.

		Note that the slots and channels of both Broadcast-Frame and Unicast-Frame slotframes are considered to avoid conflicts
		and interferences.

		:note: all 16 channels are assumed available

		:param tx: the transmitting node
		:type tx: NodeID
		:param rx: the receiving node or None if broadcast link to be scheduled
		:type rx: NodeID or None
		:param slotframe: the slotframe the link should be scheduled to
		:type slotframe: Slotframe
		:return: (slotoffset, channeloffset)
		:rtype: (int,int) tuple of (None,None) tuple if cell not found
		"""
		max_slots = 0
		for frame in self.frames.values():
			if max_slots < frame.slots:
				max_slots = frame.slots

		for slot in range(1, max_slots):
			skip = False
			free_channels = set(range(16))
			# Run through all available frames to detect channels that conflict or interfere with intended link
			for frame in self.frames.values():
				# Exclude those cells that interfere with tx->rx transmission
				free_channels = free_channels.difference(self.interfere(slot, tx, rx, frame))
				# Take next slot, if there are no channels available or the tx->rx conflicts with another link at that slot
			#if len(free_channels) != 0:
			for frame in self.frames.values():
				if len(free_channels) == 0 or self.conflict(slot, tx, rx, frame):
					skip = True
					break
			# If all previous checks are passed, pick and return the slot and channel found
			if not skip:
				#find first non blacklisted cell
				for chnl in list(free_channels):
					if not self.blacklist(chnl,slot,slotframe):
						return slot, chnl

			# If all slots of the target frame are checked without result, break and return (None,None)
			if slot == slotframe.slots-1:
				break

		return None, None

	def probed(self, node, resource, value):
		"""
		Install observer to node for statistics resource.

		Once a statistics resource has been defined, the node returns its identifier in value. This ensures an observer is
		set to node for the returned statistics resource.

		:param node: the node the statistics resource belongs to
		:type node: NodeID
		:param resource: the resource type the node has defined
		:type resource: str (practically the uri of the resource e.g. 6t/6/sm)
		:param value: the identifier of the statistics resource
		:type value: int (concatenating the resource and the value give the uri to the resource e.g. 6t/6/sm/0)
		:return: the set of commands needed to complete the installation of the observer to the resource
		:rtype: BlockQueue
		"""
		q = BlockQueue()
		q.push(Command('observe', node, terms.uri['6TP_SV'] + "/" + str(value)))
		q.block()
		return q

	def reported(self, node, resource, value):
		#because contiki gives the stats in a list of dictionaries (WTF?!) convert it here to a proper dictionary
		info = {}
		for infos in value:
			info[infos.keys()[0]] = {}
			for stat in infos[infos.keys()[0]]:
				info[infos.keys()[0]][stat.keys()[0]] = stat[stat.keys()[0]]

		self.statistics[str(node).split("]")[0].strip("[").split("::")[-1]] = info

	def rewired(self, node_id, old_parent, new_parent):
		q = BlockQueue()
		q = self.Schedule_Link(node_id,new_parent, self.frames[self.rewireframe],q)
		q = self.Schedule_Link(new_parent,node_id, self.frames[self.rewireframe],q)
		q.block()
		return [q]

	def CheckStatistic(self):
		# if self.statcheck:
		# 	return
		# self.statcheck = True
		logg.debug("Check Statistics")
		#iterate the statistics
		#TODO: check if bad link is not a lost child, in that case do nothing
		q = BlockQueue()
		for node, links in self.statistics.iteritems():
			#iterate through all links
			for link, stats in links.iteritems():
				ETX = stats["ETX"]
				if ETX < 0:
					#data not collected yet
					continue
				try:
					PRR = self.statistics[link][node]["PRR"]
					if PRR < 0:
						#data not collected yet
						continue
				except:
					#data for receiving end not available
					continue
				if ETX >= self.ETX_Ceil or PRR <= self.PRR_Floor:
					#its within parameters for blacklisting, find the the link cells in the frames
					logg.info("Detected bad link: " + str(node) + " -> " + str(link))
					for name, frame in self.frames.iteritems():
						#build a set to prevent duplicates (due to multiple link_types) with items (owner,slot,channel)
						s = Set()
						for cell in frame.get_cells_similar_to(tx_node = "aaaa::" + node, rx_node = "aaaa::" + link):
							s.add((cell.owner,cell.slot,cell.channel))
						cells = []
						#blacklist the cells
						for c in s:
							cells += self._blacklist(c[0],c[1],c[2],name,-1)
						#rescheduler the cells
						for cl in cells:
							# self.schedule(c.tx,c.rx,frame)
							q = self.Schedule_Link(cl[0],cl[1],frame,q)
						#send the changes to the network
						self.communicate([q])
					#only blacklist one link at a time to let the network adjust to the changes so break from loop
					return

if __name__ == '__main__':
	x = main.get_user_input(None)
	if isinstance(x, main.UserInput):
		sch = TrivialScheduler(x.network_name, x.lbr, x.port, x.prefix, x.visualizer)
		sch.start()
		sys.exit(0)
	sys.exit(x)