__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.12"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import sys

from core.schedule import SchedulerInterface, logg
from core.slotframe import Slotframe, Cell
from core.interface import BlockQueue
from example import main
from time import time
from util.adwin import adwin
from util import terms, logger
import logging
from txthings import coap
import os

logg = logging.getLogger('RiSCHER')

class Plexiflex(SchedulerInterface):
	"""
	"""
	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer=None):
		super(Plexiflex,self).__init__(net_name, lbr_ip, lbr_port, prefix, visualizer)
		self.metainfo = {}
		self.pending_connects = []
		# self.stats_ids = 1
		self.reserved_cells = []
		# Define a frame of size 11 slots containing unicast cells
		mainstream_frame = Slotframe("mainstream", 11)
		# Register that frame to the dictionary of frames of the parent Reflector
		self.frames[mainstream_frame.name] = mainstream_frame
		self._register_frames([mainstream_frame])

	def start(self):
		self.rewireframe = "mainstream"

		self.pending_connects.append(self.root_id)
		self.metainfo[self.root_id] = {'latency_adwin':adwin.Adwin(5), 'variance_adwin':adwin.Adwin(5), 'timestamp':-1,'pending_cells':None}
		self.communicate(self.get_neighbor_of(self.root_id, True))
		super(Plexiflex, self).start()

	def connected(self, child, parent=None, old_parent=None):
		if child not in self.pending_connects:
			self.pending_connects.append(child)
			self.metainfo[child] = {'latency_adwin':adwin.Adwin(5), 'variance_adwin':adwin.Adwin(5), 'timestamp':-1,'pending_cells':None}
			self.communicate(self.get_neighbor_of(child, True))
		return None

	def disconnected(self, node_id):
		if node_id in self.pending_connects:
			self.pending_connects.remove(node_id)
		if node_id in self.metainfo:
			del self.metainfo[node_id]
		for i in self.reserved_cells:
			if i.owner == node_id or i.tna == node_id:
				self.reserved_cells.remove(i)

	def rewired(self, node_id, old_parent, new_parent):
		pass #nothing to be done

	def framed(self, who, local_name, remote_alias, old_payload):
		q = BlockQueue()
		if who in self.pending_connects and self.metainfo[who]['pending_cells'] is not None and len(self.metainfo[who]['pending_cells']) == 0:
			self.pending_connects.remove(who)
			q.push(self._initiate_schedule(who))
		return q

	def celled(self, who, slotoffs, channeloffs, frame, linkoption, linktype, target, old_payload):
		for i in self.reserved_cells:
			if i.owner == who and i.slot == slotoffs and i.channel == channeloffs and i.slotframe == frame.get_alias_id(who):
				self.reserved_cells.remove(i)
				break
		if linkoption & 1 == 1:
			q = BlockQueue()
			cells = frame.get_cells_similar_to(
				owner=who,
				tna=self.dodag.get_parent(who),
				slot=slotoffs,
				channel=channeloffs,
				link_option=1
			)
			# if len(cells) == 1:
			# 	q.push(self.set_remote_statistics(who, self.stats_ids, cells[0], terms.resources['6TOP']['STATISTICS']['ETX']['LABEL'], 5))
			# 	self.stats_ids += 1
			return q
		return None

	def deleted(self, who, resource, info):
		pass

	def reported(self, node, resource, value):
		q = BlockQueue()
		if node in self.pending_connects:
			if str(resource) == terms.get_resource_uri('6TOP', 'SLOTFRAME') and \
					self.frames['mainstream'].get_alias_id(node) != 255:
				add = True
				for f in self.frames.values():
					parts = f.name.split('#')
					if len(parts) == 2 and parts[0] == node.eui_64_ip and int(parts[1]) == 255:
						self.frames['mainstream'].set_alias_id(node, 255)
						del self.frames[f.name]
						add = False
						break
				if add:
					q.push(self.post_slotframes(node, self.frames['mainstream']))
			elif str(resource) == terms.get_resource_uri('6TOP', 'CELLLIST', 'ID') and value is not None:
				self.metainfo[node]['pending_cells'] = value
			elif str(resource).startswith(terms.get_resource_uri('6TOP', 'CELLLIST',ID='')) and value is not None:
				self.metainfo[node]['pending_cells'].remove(value[terms.resources['6TOP']['CELLLIST']['ID']['LABEL']])
				if not self.metainfo[node]['pending_cells'] and self.frames['mainstream'].get_alias_id(node) is not None:
					self.pending_connects.remove(node)
					q.push(self._initiate_schedule(node))
		elif str(resource).startswith(terms.get_resource_uri('6TOP', 'NEIGHBORLIST')) and value is not None:
			if node != self.root_id and (not isinstance(value,dict) or "traffic" not in value):
				q.push(self._adapt(node))
			elif node != self.root_id and isinstance(value,dict) and "traffic" in value:
				logg.info("PLEXIFLEX,MESSAGE,"+ str(node)+","+str(value["traffic"]))
		elif str(resource).startswith(terms.get_resource_uri('6TOP', 'STATISTICS')) and value == coap.CHANGED:
			pass
		return q

	def _adapt(self,node):
		q = BlockQueue()
		old_avg_timelag = self.metainfo[node]['latency_adwin'].getEstimation()
		old_avg_variance = self.metainfo[node]['variance_adwin'].getEstimation()
		last = self.metainfo[node]['timestamp']
		now = time()
		self.metainfo[node]['timestamp'] = now
		if last > 0:
			timelag = now - last
			trigger_avg = self.metainfo[node]['latency_adwin'].update(timelag)
			new_avg_timelag = self.metainfo[node]['latency_adwin'].getEstimation()
			new_var_timelag = self.metainfo[node]['latency_adwin'].getVariance()
			trigger_var = self.metainfo[node]['variance_adwin'].update(new_var_timelag)
			new_avg_variance = self.metainfo[node]['variance_adwin'].getEstimation()
			logg.info("PLEXIFLEX,PROBE,"+ str(node)+","+str(timelag)+","+ str(self.metainfo[node]['latency_adwin'].length())+","+str(new_avg_timelag)+","+ str(new_var_timelag)+","+ str(self.metainfo[node]['variance_adwin'].length())+","+str(new_avg_variance))
			tmp = ""
			for c in self.frames["mainstream"].get_cells_of(node):
				tmp += str(c.slot)+"#"+str(c.channel)+","
			logg.info("PLEXIFLEX,SCHEDULE,"+ str(node)+","+tmp)
			if trigger_avg:
				logg.info("PLEXIFLEX,INTERVAL,"+ str(node)+",CHANGE")
				if old_avg_timelag < new_avg_timelag:
					so,co = self.schedule(node, self.dodag.get_parent(node), self.frames["mainstream"])
					logg.info("PLEXIFLEX,INTERVAL,"+ str(node)+",ADD("+str(so)+","+str(co)+")")
					if so is not None and co is not None:
						q.push(self.post_link(so, co, self.frames["mainstream"], node, self.dodag.get_parent(node)))
				elif old_avg_timelag > new_avg_timelag:
					cells = self.frames['mainstream'].get_cells_similar_to(owner=node,tna=self.dodag.get_parent(node),link_option=1)
					if len(cells) > 1:
						logg.info("PLEXIFLEX,INTERVAL,"+ str(node)+",REMOVE")
						so,co = self.deschedule(node, self.dodag.get_parent(node),self.frames["maintenance"])
						if so is not None and co is not None:
							q.push(self.delete_link(node, self.frames["mainstream"], so, co))
			if trigger_var:
				logg.info("PLEXIFLEX,VARIANCE,"+ str(node)+",CHANGE")
				if old_avg_variance < new_avg_variance:
					so,co = self.schedule(node, self.dodag.get_parent(node), self.frames["mainstream"])
					logg.info("PLEXIFLEX,VARIANCE,"+ str(node)+",ADD("+str(so)+","+str(co)+")")
					if so is not None and co is not None:
						q.push(self.post_link(so, co, self.frames["mainstream"], node, self.dodag.get_parent(node)))
				elif old_avg_variance > new_avg_variance:
					cells = self.frames['mainstream'].get_cells_similar_to(owner=node,tna=self.dodag.get_parent(node),link_option=1)
					if len(cells) > 1:
						logg.info("PLEXIFLEX,VARIANCE,"+ str(node)+",REMOVE")
						self.deschedule(node, self.dodag.get_parent(node),self.frames["maintenance"])
						if so is not None and co is not None:
							q.push(self.delete_link(node, self.frames["mainstream"], so, co))
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
				free_channels = free_channels.difference(self.interfere(slot, tx, rx, frame, self.reserved_cells))
				# Take next slot, if there are no channels available or the tx->rx conflicts with another link at that slot

			for frame in self.frames.values():
				if len(free_channels) == 0 or self.conflict(slot, tx, rx, frame, self.reserved_cells):
					skip = True
					break

			# If all previous checks are passed, pick and return the slot and channel found
			if not skip:
				return slot, list(free_channels)[0]

			# If all slots of the target frame are checked without result, break and return (None,None)
			if slot == slotframe.slots-1:
				break

		return None, None

	def deschedule(self, tx, rx, slotframe):
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

		so = None
		co = None
		cells = slotframe.get_cells_similar_to(owner=tx,tna=rx,link_option=1)
		if len(cells) == 1:
			so = cells[0].slot
			co = cells[0].channel
			cells = slotframe.get_cells_similar_to(owner=rx,tna=tx,link_option=2)
			if len(cells) == 1 and so == cells[0].slot and co == cells[0].channel:
				return so,co
			else:
				logg.critical("plexiflex in panic. did not find expected cell")
		return None, None


	def _initiate_schedule(self, node):
		cells = self.frames['mainstream'].get_cells_of(node)
		dag_neighbors = []
		parent = self.dodag.get_parent(node)
		if parent:
			dag_neighbors += [parent]
		#children = self.dodag.get_children(node)
		#if children:
		#	dag_neighbors += children
		q = BlockQueue()
		for neighbor in dag_neighbors:
			flags = 0
			for cell in cells:
				if cell.tna == neighbor:
					if cell.option & 1 == 1:
						flags |= 1
					elif cell.option & 2 == 2:
						flags |= 2
			if flags & 1 == 0:
				so,co = self.schedule(node, neighbor, self.frames["mainstream"])
				if so is not None and co is not None:
					q.push(self.post_link(so, co, self.frames["mainstream"], node, neighbor))
					self.reserved_cells.append(Cell(node,so,co,self.frames["mainstream"].get_alias_id(node),0,1,neighbor))
					self.reserved_cells.append(Cell(neighbor,so,co,self.frames["mainstream"].get_alias_id(neighbor),0,2,node))
				else:
					logg.critical("INSUFFICIENT SLOTS: node " + str(node) + " cannot use more cells")
			if flags & 2 == 0:
				so,co = self.schedule(neighbor, node, self.frames["mainstream"])
				if so is not None and co is not None:
					q.push(self.post_link(so, co, self.frames["mainstream"], neighbor, node))
					self.reserved_cells.append(Cell(node,so,co,self.frames["mainstream"].get_alias_id(node),0,2,neighbor))
					self.reserved_cells.append(Cell(neighbor,so,co,self.frames["mainstream"].get_alias_id(neighbor),0,1,node))
				else:
					logg.critical("INSUFFICIENT SLOTS: node " + str(neighbor) + " cannot use more cells")
		return q

if __name__ == '__main__':
	x = main.get_user_input(None)
	if isinstance(x, main.UserInput):
		v = {
			"name"	:	"plexi1",
			"Key"	:	os.path.join("keys", "plexi1.key_secret"),
			"VHost"	:	None
		}
		sch = Plexiflex(x.network_name, x.lbr, x.port, x.prefix, v)
		sch.start()
		sys.exit(0)
	sys.exit(x)