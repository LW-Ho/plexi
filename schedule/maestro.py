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
		return str(self.id) + ': ' + self.op + ' ' + str(self.to) + ' ' + str(self.uri) + ' ' + str(self.payload) + ' ' + str(self.callback)


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
				self.send_command(comm, self.count_sessions)
				if self.count_sessions not in self.sessions or len(self.sessions[self.count_sessions]) == 0:
					break
				comm = self.sessions[self.count_sessions].pop()

	def _touch_session(self, command_token):
		if command_token in self.cache and self.cache[command_token]["session"] in self.sessions:
			session = self.sessions[self.cache[command_token]["session"]]
			session.achieved(self.cache[command_token]["id"])
			if not session.finished():
				comm = session.pop()
				while comm:
					self.send_command(comm, self.cache[command_token]["session"])
					if len(session) == 0:
						break
					comm = session.pop()
			else:
				del self.sessions[self.cache[command_token]["session"]]

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
		logg.debug("Children list from " + str(response.remote[0]) + " >> " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
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
		local_fd = payload['fd']
		old_payload = self.cache[tk]['payload']
		frame = old_payload['frame']
		self._decache(tk)
		self._create_session(self._frame(node_id, frame, local_fd, old_payload))
		self._create_session(self.framed(node_id, frame, local_fd, old_payload))

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
# parser.clean_payload(response.payload)
		print response
		logg.debug("Node " + str(response.remote[0]) + " replied on a cell post with " + response.payload + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		cell_cd = payload['cd']
		old_payload = self.cache[tk]['payload']
		frame = old_payload['frame']
		so = old_payload['so']
		co = old_payload['co']

		self._decache(tk)
		self._create_session(self.celled(node_id, so, co, frame, cell_cd, old_payload))

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
				self.send_command(comm)

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
				self.send_command(comm)

	def send_commands(self, commands):
		if isinstance(commands, queue.RendezvousQueue):
			self._create_session(commands)

	def send_command(self, comm, session):
		if isinstance(comm, Command):
			self.cache[comm.id] = {'session': session, 'id': comm.id, 'op': comm.op, 'to': comm.to, 'uri': comm.uri}
			if comm.payload:
				self.cache[comm.id]['payload'] = comm.payload.copy()
				if isinstance(comm.payload, dict) and 'frame' in comm.payload:
					if comm.uri == terms.uri['6TP_SF']:
						comm.payload = {'ns': comm.payload['frame'].slots}
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

		q = queue.RendezvousQueue()
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
		q = queue.RendezvousQueue()
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_links_of(node_id)
			for cell in deleted_cells:
				if cell.owner != node_id:
					comm = Command('delete', cell.owner, terms.uri['6TP_CL']+'/'+str(cell.id))
					q.push(comm.id, comm)
			del frame.fds[node_id]
		q.bank()
		return q

	def _frame(self, who, frame, remote_fd, old_payload):
		logg.info(str(who) + " installed new " + frame.name + " frame with id=" + str(remote_fd))
		frame.set_alias_id(who, remote_fd)
		return None

	def _cell(self, who, slotoffs, channeloffs, frame, remote_cell_id, old_payload):
		logg.info(str(who) + " installed new cell (id=" + str(remote_cell_id) + ") in frame " + frame.name + " at slotoffset=" + str(slotoffs) + " and channel offset=" + str(channeloffs))
		return None

	def start(self):
		raise NotImplementedError()

	def popped(self, node):
		pass

	def connected(self, child, parent, old_parent=None):
		pass

	def disconnected(self, node_id):
		pass

	def framed(self, who, local_name, remote_alias, old_payload):
		pass

	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		pass

	def probed(self, node_id, metric_id):
		pass

	def reported(self, node_id, endpoint, metric_values):
		pass


class Scheduler(Reflector):

	def get_remote_frame(self, node, slotframe):  # TODO: observe (makes sense when distributed scheduling in place)
		assert isinstance(node, NodeID)
		assert isinstance(slotframe, Slotframe)
		pass # TODO self.commands.append(self.Command('post', node, terms.uri['6TP_SF'], {'frame': slotframe}))

	def set_remote_frames(self, node, slotframes):
		assert isinstance(node, NodeID)
		assert isinstance(slotframes, Slotframe) #TODO or isinstance(slotframes, array)
		q = queue.RendezvousQueue()
		for item in [slotframes] if isinstance(slotframes, Slotframe) else slotframes:
			comm = Command('post', node, terms.uri['6TP_SF'], {'frame': item})
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

		q = queue.RendezvousQueue()

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
			comm = Command('post', c.owner, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'fd':c.slotframe,'frame': slotframe, 'lo':c.option, 'lt':c.type})
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
		q = queue.RendezvousQueue()
		comm = Command('get' if not observe else 'observe', node, terms.uri['RPL_OL'])
		q.push(comm.id, comm)
		q.bank()
		return q

	def get_remote_statistics(self, node, statistics, observe=False):
		pass

	def disconnect_node(self, node):
		pass

	def conflict(self, slot, tx, rx, slotframe):
		assert slotframe in self.frames
		for item in slotframe.cell_container:
			if item.slot == slot:
				if item.rx_node == tx or (item.rx_node is None and (item.tx_node == self.dodag.get_parent(tx) or item.tx_node in self.dodag.get_children(tx))):
					return True
				elif item.tx_node == tx:
					depends = None
				elif (item.rx_node is not None and item.rx_node == rx) or \
						(item.rx_node is None and rx is not None and (item.tx_node == self.dodag.get_parent(rx) or item.tx_node in self.dodag.get_children(rx))) or \
						(item.rx_node is not None and rx is None and (tx == self.dodag.get_parent(item.rx_node) or tx in self.dodag.get_children(item.rx_node))) or \
						(rx is None and item.rx_node is None and
								 not set(self.dodag.get_children(tx).append(self.dodag.get_parent(tx))).isdisjoint(
									 set(self.dodag.get_children(item.tx_node).append(self.dodag.get_parent(item.tx_node)))
								 )):
					return True
		return False

	def interfere(self, slot, tx, rx, slotframe):
		assert slotframe in self.frames
		channels = []
		for item in slotframe.cell_container:
			if item.slot == slot and item.rx_node is not None and rx is not None and \
				item.rx_node not in self.dodag.get_children(tx).append(self.dodag.get_parent(tx)) and \
				rx not in self.dodag.get_children(item.tx_node).append(self.dodag.get_parent(item.tx_node)):
				channels.append(item.channel)
		return channels


	def schedule(self, tx, rx, slotframe):
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
		#super(TrivialScheduler, self).start()
		#self.rb_flag = 0

		self.send_commands(self.get_remote_children(self.root_id))
		f1 = Slotframe("Broadcast-Frame", 25)
		self.frames[f1.name] = f1
		q = self.set_remote_frames(self.root_id, f1)
		q.append(self.set_remote_link(1, 0, f1, self.root_id, None, self.root_id))
		self.send_commands(q)
#		print q

#		f2 = Slotframe("Unicast-Frame", 21)
#		self.frames[f2.name] = f2
#		self.send_commands(self.set_remote_frames(self.root_id, f2))
		self.client.start()

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
