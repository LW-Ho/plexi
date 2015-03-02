__author__ = "Dimitris Sarakiotis, Ilker Oztelcan, George Exarchakos"
__email__ = "d.sarakiotis@tue.nl, i.oztelcan@tue.nl, g.exarchakos@tue.nl"
__version__ = "0.0.27"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from endpoint.client import Communicator, LazyCommunicator
from schedule.graph import DoDAG
from resource.rpl import NodeID
from util import parser, logger
import json
from schedule.slotframe import Slotframe, Cell
from util import terms, exception
from txthings import coap
import logging
from util import queue
from util.warn import deprecated

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)

class Command(object):
	token = 0
	def __init__(self, op, to, uri, payload=None, callback=None):
		self.id = Command.token
		Command.token += 1
		self.op = op
		self.to = to
		self.uri = uri
		self.payload = payload
		self.callback = callback

	def __str__(self):
		return str(id) + ': ' + self.op + ' ' + str(self.to) + ' ' + str(self.uri) + ' ' + str(self.payload) + ' ' + str(self.callback)


class Reflector(object):

	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer=False):
		NodeID.prefix = prefix
		self.root_id = NodeID(lbr_ip, lbr_port)
		logg.info("Scheduler started with LBR=" + str(self.root_id))
		self.client = LazyCommunicator(5)
		self.dodag = DoDAG(net_name, self.root_id, visualizer)
		self.frames = {}
		self.cache = {}
		self.sessions = {}
		self.count_sessions = 0

	def start(self):
		q = queue.MilestoneQueue()
		#self.commander(self.Command('observe', self.root_id, terms.uri['RPL_NL']))
		comm = Command('observe', self.root_id, terms.uri['RPL_OL'])
		q.push(comm.id, comm)
		#self.commander(self.Command('post', self.root_id, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"}))
		self._create_session(q)

	def _decache(self, token):
		if token:
			sent_msg = self.cache[token]
			if sent_msg['op'] != 'observe':
				del self.cache[token]

	def _create_session(self, milestone_queue):
		if milestone_queue and len(milestone_queue) > 0:
			self.count_sessions += 1
			self.sessions[self.count_sessions] = milestone_queue
			comm = self.sessions[self.count_sessions].pop()
			while comm:
				self.commander(comm, self.count_sessions)
				comm = self.sessions[self.count_sessions].pop()

	def _touch_session(self, command_token):
		if command_token in self.cache and self.cache[command_token]["session"] in self.sessions:
			session = self.sessions[self.cache[command_token]["session"]]
			session.achieved(self.cache[command_token]["id"])
			if len(session) > 0:
				comm = session._pop()
				while comm:
					self.commander(comm, self.cache[command_token]["session"])
			else:
				del self.sessions[self.cache[command_token]["session"]]

	@deprecated
	def _observe_rpl_nodes(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		sender = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(sender) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Observed node list from " + str(response.remote[0]) + " >> " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		self._decache(tk)
		for n in payload:
			node = NodeID(str(n))
			if self.dodag.attach_node(node):
				commands = self._pop(node)
				if commands:
					for comm in commands:
						self.commander(comm)

	def _observe_rpl_children(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return

		self._touch_session(tk)
		parent_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(parent_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		#TODO if an existing observer is detected, the scheduler has previously lost contact with the network. The whole topology has to be rebuilt
		logg.debug("Observed children list from " + str(response.remote[0]) + " >> " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))

		observed_children = []
		for n in payload:
			observed_children.append(NodeID(str(n)))

		self._decache(tk)
		dodag_child_list = self.dodag.get_children(parent_id)

		removed_nodes = [item for item in dodag_child_list if item not in observed_children]
		for n in removed_nodes:
			if self.dodag.detach_node(n):
				self._create_session(self._disconnect(n))
				self._create_session(self.disconnected(n))
		for k in observed_children:
			old_parent = self.dodag.get_parent(k)
			if self.dodag.attach_child(k, parent_id):
				self._create_session(self._connect(k, parent_id, old_parent))
				self._create_session(self.connected(k, parent_id, old_parent))

	def _receive_slotframe_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		self._touch_session(tk)
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Node " + str(response.remote[0]) + " replied on a slotframe post with " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		frame_alias = payload['fd']
		old_payload = self.cache[tk]['payload']
		frame_name = old_payload['frame']
		self._decache(tk)
		self._create_session(self._frame(node_id, frame_name, frame_alias, old_payload))
		self._create_session(self.framed(node_id, frame_name, frame_alias, old_payload))

	def _receive_cell_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		self._touch_session(tk)
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Node " + str(response.remote[0]) + " replied on a cell post with " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		cell_cd = payload['cd']
		old_payload = self.cache[tk]['payload']
		frame_name = old_payload['frame']
		so = old_payload['so']
		co = old_payload['co']

		self._decache(tk)
		self._create_session(self.celled(node_id, so, co, frame_name, cell_cd, old_payload))

	def _receive_cell_info(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		self._touch_session(tk)
		node_id = NodeID(response.remote[0], response.remote[1])
		if node_id not in self.dodag.graph.nodes():
			self._decache(tk)
			return
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Node " + str(response.remote[0]) + " replied on a cell get/delete with " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		self._decache(tk)


	def _receive_statistics_metrics_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Node " + str(response.remote[0]) + " replied on statistics post with " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		metric_id = payload[terms.keys['SM_ID']]
		self._decache(tk)
		commands = self.probed(node_id, metric_id)
		if commands:
			for comm in commands:
				self.commander(comm)

	def _receive_statistics_metrics_value(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if node_id not in self.dodag.graph.nodes():
			self._decache(tk)
			return
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Observed statistics from " + str(response.remote[0]) + " >> " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = []
		try:
			payload = json.loads(parser.clean_payload(response.payload))
		except Exception:
			self._decache(tk)
			return
		self._decache(tk)
		commands = []
		for item in payload:
			for (neighbor, statistics) in item.items():
				endpoint = NodeID(neighbor)
				if endpoint not in self.dodag.graph.nodes():
					continue
				for metrics in statistics:
					for (key, value) in metrics.items():
						self.dodag.update_link(node_id, endpoint, str(key), value)
				if self.dodag.graph.has_edge(node_id, endpoint) and 'statistics' in self.dodag.graph.edge[node_id][endpoint]:
					commands = self.reported(node_id, endpoint, self.dodag.graph.edge[node_id][endpoint]['statistics'])
		if commands:
			for comm in commands:
				self.commander(comm)

	def commander(self, comm, session):
		if isinstance(comm, Command):
			self.cache[comm.id] = {'session': session, 'id': comm.id, 'op': comm.op, 'to': comm.to, 'uri': comm.uri}
			if comm.payload:
				self.cache[comm.id]['payload'] = comm.payload.copy()
				if isinstance(comm.payload, dict) and 'frame' in comm.payload:
					if comm.uri == terms.uri['6TP_SF']:
						comm.payload = {'ns': self.frames[comm.payload['frame']].slots}
					elif comm.uri == terms.uri['6TP_CL']:
						del comm.payload['frame']
			if not comm.callback:
				if comm.uri == terms.uri['RPL_NL']:
					comm.callback = self._observe_rpl_nodes
				elif comm.uri == terms.uri['RPL_OL']:
					comm.callback = self._observe_rpl_children
				elif comm.uri == terms.uri['6TP_SF']:
					comm.callback = self._receive_slotframe_id
				elif comm.uri == terms.uri['6TP_CL']:
					comm.callback = self._receive_cell_id
				elif comm.uri == terms.uri['6TP_SM']:
					comm.callback = self._receive_statistics_metrics_id
				elif comm.uri.startswith(terms.uri['6TP_SV']+"/0"):
					comm.callback = self._receive_statistics_metrics_value
				elif comm.uri.startswith(terms.uri['6TP_CL']):
					comm.callback = self._receive_cell_info
			logg.info("Sending to " + str(comm.to) + " >> " + comm.op + " " + comm.uri + " -- " + str(comm.payload))
			if comm.op == 'get':
				self.client.GET(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'observe':
				self.client.OBSERVE(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'post':
				self.client.POST(comm.to, comm.uri, parser.construct_payload(comm.payload), comm.id, comm.callback)
			elif comm.op == 'delete':
				self.client.DELETE(comm.to, comm.uri, comm.id, comm.callback)

	def _pop(self, node):
		logg.info(str(node) + ' popped up')
		return None

	def _connect(self, child, parent, old_parent=None):
		if old_parent:
			logg.info(str(child) + ' rewired to ' + str(parent) + ' from ' + str(old_parent))
		else:
			logg.info(str(child) + ' wired to parent ' + str(parent))

		q = queue.MilestoneQueue()
		rpl_ol = Command('observe', child, terms.uri['RPL_OL'])
		q.push(rpl_ol.id, rpl_ol)
		# TODO: commands.append(self.Command('post', child, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"})) # First step of statistics installation.
		for k in self.frames.keys():
			comm = Command('post', child, terms.uri['6TP_SF'], {'frame': k})
			q.push(comm.id, comm)
		q.bank()
		return q

	def _disconnect(self, node_id):
		logg.info(str(node_id) + " was removed from the network")
		q = queue.MilestoneQueue()
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_links_of(node_id)
			for cell in deleted_cells:
				if cell.owner != node_id:
					comm = Command('delete', cell.owner, terms.uri['6TP_CL']+'/'+str(cell.id))
					q.push(comm.id, comm)
			del frame.fds[node_id]
		q.bank()
		return q

	def _frame(self, who, local_name, remote_alias, old_payload):
		logg.info(str(who) + " installed new " + local_name + " frame with id=" + str(remote_alias))
		self.frames[local_name].set_alias_id(who, remote_alias)
		return None

	def _cell(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		logg.info(str(who) + " installed new cell (id=" + str(remote_cell_id) + ") in frame " + frame_name + " at slotoffset=" + str(slotoffs) + " and channel offset=" + str(channeloffs))
		return None

	def popped(self, node):
		raise NotImplementedError()

	def connected(self, child, parent, old_parent=None):
		raise NotImplementedError()

	def disconnected(self, node_id):
		raise NotImplementedError()

	def framed(self, who, local_name, remote_alias, old_payload):
		raise NotImplementedError()

	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		raise NotImplementedError()

	def probed(self, node_id, metric_id):
		raise NotImplementedError()

	def reported(self, node_id, endpoint, metric_values):
		raise NotImplementedError()


class Scheduler(Reflector):

	def get_remote_frame(self, node, slotframe):  # TODO: observe (makes sense when distributed scheduling in place)
		assert isinstance(node, NodeID)
		assert isinstance(slotframe, Slotframe)
		pass # TODO self.commands.append(self.Command('post', node, terms.uri['6TP_SF'], {'frame': slotframe}))

	def set_remote_frame(self, node, slotframe):
		assert isinstance(node, NodeID)
		assert isinstance(slotframe, Slotframe)
		q = queue.MilestoneQueue()
		comm = Command('post', node, terms.uri['6TP_SF'], {'frame': slotframe})
		q.push(comm.id, comm)
		q.bank()
		return q

	def get_remote_cell(self, node, cell): # TODO: observe (make sense when distributed scheduling in place)
		pass

	def set_remote_link(self, slot, channel, slotframe, source, destination, target=None):
		assert isinstance(slotframe, Slotframe)
		assert channel <= 16
		assert slot < slotframe.slots
		assert destination is None or isinstance(target, NodeID)
		assert isinstance(source, NodeID)
		assert destination is None or isinstance(destination, NodeID)

		q = queue.MilestoneQueue()

		if target and target != source and target != destination:
			return False

		found_tx = None
		found_rx = []
		for c in slotframe.cell_container:
			if c.slot == slot and c.channel == channel:
				if destination is not None and c.tx_node == source and c.rx_node == destination:
					if c.link_option == 1:
						found_tx = c.owner
					elif c.link_option == 2:
						found_rx.append(c.owner)
				elif destination is None:
					if c.tx_node == source and c.rx_node is None:
						if c.link_option == 9:
							found_tx = c.owner
						elif c.link_option == 10:
							found_rx.append(c.owner)
		cells = []
		if destination is not None:
			if not found_tx and (target is None or target == source):
				cells.append(Cell(source, slot, channel, source, destination, slotframe.get_alias_id(source), 0, 1))
			if destination not in found_rx and (target is None or target == destination):
				cells.append(Cell(destination, slot, channel, source, destination, slotframe.get_alias_id(destination), 0, 2))
		elif destination is None:
			neighbors = [self.dodag.get_parent(source)]+self.dodag.get_children(source) if self.dodag.get_parent(source) else []+self.dodag.get_children(source)
			if target is None or target == source:
				if not found_tx:
					cells.append(Cell(source, slot, channel, source, destination, slotframe.get_alias_id(source), 1, 9))
				tmp = [item for item in neighbors if item not in found_rx]
				for neighbor in tmp:
					cells.append(Cell(neighbor, slot, channel, source, destination, slotframe.get_alias_id(neighbor), 1, 10))
			elif target and target != source and target in neighbors and target not in found_rx:
				cells.append(Cell(target, slot, channel, source, destination, slotframe.get_alias_id(target), 1, 10))

		depth_groups = {}
		for c in cells:
			slotframe.cell_container.append(c)
			comm = Command('post', c.owner, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'fd':c.slotframe_id,'frame': slotframe.name, 'lo':c.link_option, 'lt':c.link_type})
			depth = self.dodag.get_node_depth(c.owner)
			if depth not in depth_groups:
				depth_groups[depth] = [comm]
			else:
				depth_groups[depth].append(comm)
		for j in sorted(depth_groups.keys(), reverse=True):
			for k in depth_groups[j]:
				q.push(k.id, k)
			q.bank()

		return q

	def get_remote_children(self, node, observe=False):
		assert isinstance(node, NodeID)
		q = queue.MilestoneQueue()
		comm = Command('get' if not observe else 'observe', node, terms.uri['RPL_OL'])
		q.push(comm.id, comm)
		q.bank()
		return q

	def get_remote_statistics(self, node, statistics, observe=False):
		pass

	def disconnect_node(self, node):
		pass



class TrivialScheduler(Scheduler):
	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer):
		super(TrivialScheduler, self).__init__(net_name, lbr_ip, lbr_port, prefix, visualizer)
		self.slot_counter = 2
		self.channel_counter = 0
		self.b_slot_counter = 2
		self.pairs = []
		self.commands_waiting = []

	def start(self):
		super(TrivialScheduler, self).start()
		f1 = Slotframe("Broadcast-Frame", 25)
		f2 = Slotframe("Unicast-Frame", 21)
		self.frames[f1.name] = f1
		self.frames[f2.name] = f2
		self.rb_flag = 0
		#for k in self.frames.keys():
		#	self.commander(self.Command('post', self.root_id, terms.uri['6TP_SF'], {'frame': k}))
		cb_root = Cell(1, 0, self.root_id, None, None, 1, 10)
		self.frames['Broadcast-Frame'].cell_container.append(cb_root)
		#self.client.start()     # this has to be the last line of the start function ... ALWAYS

	def _pop(self, node):
		logg.info(str(node) + ' popped up')

	def _connect(self, child, parent, old_parent=None):
		if old_parent:
			logg.info(str(child) + ' rewired to ' + str(parent) + ' from ' + str(old_parent))
		else:
			logg.info(str(child) + ' wired to parent ' + str(parent))

		commands = []

		commands.append(self.Command('observe', child, terms.uri['RPL_OL']))
		commands.append(self.Command('post', child, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"})) # First step of statistics installation.

		for k in self.frames.keys():
			commands.append(self.Command('post', child, terms.uri['6TP_SF'], {'frame': k}))

		c_flag = False

		if self.b_slot_counter >= self.frames["Broadcast-Frame"].slots:
					print("out of broadcast cells")
					return False

		if parent not in self.frames["Broadcast-Frame"].fds:
			sf_id = None
		else:
			sf_id = self.frames["Broadcast-Frame"].fds[parent]

		self.schedule_broadcast(child, sf_id)

		while c_flag == False:
			c_flag = self.check_unicast_conflict(child, parent)
			if self.slot_counter >= self.frames["Unicast-Frame"].slots:
				print("ERROR: We are out of slots!")
				return False

		if parent not in self.frames["Unicast-Frame"].fds:
			sf_id = None
		else:
			sf_id = self.frames["Unicast-Frame"].fds[parent]

		self.schedule_unicast(child, parent, sf_id)

		c_flag = False
		while c_flag == False:
			c_flag = self.check_unicast_conflict(parent, child)
			if self.slot_counter >= self.frames["Unicast-Frame"].slots:
				print("ERROR: We are out of slots!")
				return False

		if parent not in self.frames["Unicast-Frame"].fds:
			sf_id = None
		else:
			sf_id = self.frames["Unicast-Frame"].fds[parent]

		self.schedule_unicast(parent, child, sf_id)

		self.pairs.append((parent,child))

		return commands

	def _disconnect(self, node_id):
		logg.info(str(node_id) + " was removed from the network")
		commands = []
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_cell(node_id)
			for cell in deleted_cells:
				to = cell.tx_node if cell.link_option in [1, 10] else cell.rx_node
				if to != node_id:
					commands.append(self.Command('delete', to, terms.uri['6TP_CL']+'/'+str(cell.cell_id)))
			del frame.fds[node_id]
		return commands

	def _frame(self, who, local_name, remote_alias, old_payload):
		logg.info(str(who) + " installed new " + local_name + " frame with id=" + str(remote_alias))
		self.frames[local_name].set_alias_id(who, remote_alias)
		commands = []

		parent = self.dodag.get_parent(who)

		for c in self.frames[local_name].cell_container:
			if (c.tx_node == who and c.rx_node == None and c.link_option == 10) or (c.tx_node == who and parent is not None and c.rx_node == parent and c.link_option == 1) or (c.rx_node == who and c.tx_node == None and c.link_option == 9) or (c.rx_node == who and parent is not None and c.tx_node == parent and c.link_option == 2):
				c.slotframe_id = remote_alias
				#print str(self.Command('post', who, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'fd':c.slotframe_id,'frame': local_name, 'lo':c.link_option, 'lt':c.link_type}))
				commands.append(self.Command('post', who, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'fd':c.slotframe_id,'frame': local_name, 'lo':c.link_option, 'lt':c.link_type}))
			elif c.pending == True and (c.tx_node == who or c.rx_node == who):
				c.pending = False
				commands.append(self.Command('post', who, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'fd':c.slotframe_id,'frame': local_name, 'lo':c.link_option, 'lt':c.link_type}))

 		return commands


	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		logg.info(str(who) + " installed new cell (id=" + str(remote_cell_id) + ") in frame " + frame_name + " at slotoffset=" + str(slotoffs) + " and channel offset=" + str(channeloffs))
		commands = []

		parent = self.dodag.get_parent(who)

		for item in self.frames[frame_name].cell_container:
			if item.slot == slotoffs and item.channel == channeloffs:
				if item.link_option == old_payload["lo"] and item.cell_id is None:
					item.cell_id = remote_cell_id
					if item.rx_node:
						self.dodag.update_link(item.tx_node, item.rx_node, 'SLT', '++')
					else:
						self.dodag.update_node(item.tx_node, 'SLT', '++')
				elif item.cell_id is None and ((item.rx_node == parent and item.tx_node == None and item.link_option == 9) or (item.rx_node == parent and item.tx_node == who and item.link_option == 2) or (item.rx_node == who and item.tx_node == parent and item.link_option == 1)):
					if item.slotframe_id is None and parent in self.frames[frame_name].fds:
						item.slotframe_id = self.frames[frame_name].fds[parent]
					elif item.slotframe_id is None and parent not in self.frames[frame_name].fds:
						item.pending = True
						continue
					commands.append(self.Command('post', parent, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': frame_name, 'lo': item.link_option, 'lt':item.link_type}))
					# print str(self.Command('post', parent, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': frame_name, 'lo': item.link_option, 'lt':item.link_type}))

		return commands

	def schedule_unicast(self, tx_node, rx_node, sf_id):

		ct = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, None, 0,1)
		cr = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, None, 0,2)

		self.frames["Unicast-Frame"].cell_container.append(ct)
		self.frames["Unicast-Frame"].cell_container.append(cr)

		self.channel_counter = self.channel_counter + 1
		if self.channel_counter == 17 :
			print("ERROR: We are out of channels!")
			return False

		#self.commands.append(self.Command('post',tx_node ,terms.uri['6TP_CL'],{'so':ct.slot, 'co':ct.channel, 'fd':ct.slotframe_id, 'lo':ct.link_option, 'lt':ct.link_type}))
		#self.commands.append(self.Command('post',rx_node ,terms.uri['6TP_CL'],{'so':cr.slot, 'co':cr.channel, 'fd':cr.slotframe_id, 'lo':cr.link_option, 'lt':cr.link_type}))

	def check_unicast_conflict(self, child, parent):

		for item in self.frames["Broadcast-Frame"].cell_container:
			if item.slot == self.slot_counter:
				self.slot_counter = self.slot_counter + 1
				self.channel_counter = 0
				return False

		for item in self.frames["Unicast-Frame"].cell_container:        #Add something for no items in container cond. else it will give an error.
			if (item.slot == self.slot_counter) and (item.tx_node == parent or item.rx_node == parent):
				self.slot_counter = self.slot_counter + 1
				self.channel_counter = 0
				return False

		return True

	def schedule_broadcast(self, tx_node, sf_id):

		for item in self.frames["Broadcast-Frame"].cell_container:
			if item.slot == self.b_slot_counter: #larger slotframe might conflict with smaller one.
				self.b_slot_counter = self.b_slot_counter + 1

		for item in self.frames["Unicast-Frame"].cell_container:
			if item.slot == self.b_slot_counter:
				self.b_slot_counter = self.b_slot_counter + 1


		cb_brd = Cell(self.b_slot_counter, 0, tx_node, None, None, 1, 10)           # create a broadcast cell
		self.frames["Broadcast-Frame"].cell_container.append(cb_brd)                # adds the created cell to the broadcast_slotframe


		cb_nb = Cell(self.b_slot_counter, 0, None, self.dodag.get_parent(tx_node), sf_id, 1, 9)
		self.frames["Broadcast-Frame"].cell_container.append(cb_nb)
		for item in self.frames["Broadcast-Frame"].cell_container:
			if item.link_option != 7 and item.tx_node and item.tx_node == self.dodag.get_parent(tx_node):
				cb_nb2 = Cell(item.slot, 0, None, tx_node, None, 1, 9)
				self.frames["Broadcast-Frame"].cell_container.append(cb_nb2)
		self.b_slot_counter = self.b_slot_counter + 1


	def probed(self, node_id, metric_id):
		logg.info(str(node_id) + " installed statistics observer with id=" + str(metric_id))
		commands = []

		id_appended_uri = terms.uri['6TP_SV'] + "/" + str(metric_id)
		commands.append(self.Command('observe', node_id, id_appended_uri))

		return commands

	def reported(self, node_id, endpoint, statistics):
		if node_id in statistics:
			logg.info(str(node_id) + " for " + str(endpoint) + " reported >> " + str(statistics[node_id]))
