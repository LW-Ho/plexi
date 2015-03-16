__author__ = "Dimitris Sarakiotis, Ilker Oztelcan, George Exarchakos"
__email__ = "d.sarakiotis@tue.nl, i.oztelcan@tue.nl, g.exarchakos@tue.nl"
__version__ = "0.0.27"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from core.interface import Command

from core.client import LazyCommunicator
from core.graph import DoDAG
from core.node import NodeID
from util import parser
import json
from core.slotframe import Slotframe, Cell
from util import terms, exception, logger
from txthings import coap
import logging
from core import interface
import copy

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)


class Reflector(object):
	"""
	Handle all the communication with the RICH network.
	"""

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
		entry = None
		if token is not None:
			entry = self.cache[token]
			if entry['command'].op != 'observe':
				del self.cache[token]
		return entry

	def _create_session(self, assembly):
		if assembly and len(assembly) > 0:
			self.count_sessions += 1
			self.sessions[self.count_sessions] = assembly
			comm = self.sessions[self.count_sessions].pop()
			while comm:
				self._push_command(comm, self.count_sessions)
				if self.count_sessions not in self.sessions or len(self.sessions[self.count_sessions]) == 0:
					break
				comm = self.sessions[self.count_sessions].pop()

	def _touch_session(self, achieved_comm, session_id):
		if session_id in self.sessions:
			session = self.sessions[session_id]
			session.unblock(achieved_comm)
			if not session.finished():
				comm = session.pop()
				while comm:
					self._push_command(comm, session_id)
					comm = session.pop()
			else:
				del self.sessions[session_id]

	def _observe_rpl_children(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		session_id = self.cache[tk]["session"]
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
		cached_entry = self._decache(tk)
		dodag_child_list = self.dodag.get_children(parent_id)

		removed_nodes = [item for item in dodag_child_list if item not in observed_children]
		for n in removed_nodes:
			if self.dodag.detach_node(n):
				self.communicate(self._disconnect(n))
				self.communicate(self.disconnected(n))
		for k in observed_children:
			old_parent = self.dodag.get_parent(k)
			if self.dodag.attach_child(k, parent_id):
				self.communicate(self._connect(k, parent_id, old_parent))
				self.communicate(self.connected(k, parent_id, old_parent))
		self._touch_session(cached_entry['command'], session_id)

	def _receive_slotframe_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		session_id = self.cache[tk]["session"]
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		logg.debug("Node " + str(response.remote[0]) + " replied on a slotframe post with " + parser.clean_payload(response.payload) + " i.e. MID:" + str(response.mid))
		payload = json.loads(parser.clean_payload(response.payload))
		local_fd = payload['fd']
		old_payload = self.cache[tk]['command'].payload
		frame = old_payload['frame']
		cached_entry = self._decache(tk)
		self.communicate(self._frame(node_id, frame, local_fd, old_payload))
		self.communicate(self.framed(node_id, frame, local_fd, old_payload))
		self._touch_session(cached_entry['command'], session_id)

	def _receive_cell_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		session_id = self.cache[tk]["session"]
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		clean_payload = parser.clean_payload(response.payload)
		logg.debug("Node " + str(response.remote[0]) + " replied on a cell post with " + clean_payload + " i.e. MID:" + str(response.mid))
		payload = json.loads(clean_payload)
		cell_cd = payload['cd']
		old_payload = self.cache[tk]['command'].payload
		frame = old_payload['frame']
		so = old_payload['so']
		co = old_payload['co']

		cached_entry = self._decache(tk)
		self.communicate(self._cell(node_id, so, co, frame, cell_cd, old_payload))
		self.communicate(self.celled(node_id, so, co, frame, cell_cd, old_payload))
		self._touch_session(cached_entry['command'], session_id)

	def _receive_probe(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		cache_entry = self.cache[tk]
		session_id = cache_entry["session"]
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(cache_entry)
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		clean_payload = parser.clean_payload(response.payload)
		logg.debug("Node " + str(response.remote[0]) + " replied on a probe with " + clean_payload + " i.e. MID:" + str(response.mid))
		payload = json.loads(clean_payload)
		info = None
		if cache_entry['command'].uri == terms.uri['6TP_CL']:
			info = payload
		elif cache_entry['command'].uri == terms.uri['6TP_SM']:
			info = payload[terms.keys['SM_ID']]
		cached_entry = self._decache(tk)
		self.communicate(self._probe(node_id, cache_entry['command'].uri, info))
		self.communicate(self.probed(node_id, cache_entry['command'].uri, info))
		self._touch_session(cached_entry['command'], session_id)

	def _receive_report(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		cache_entry = self.cache[tk]
		session_id = cache_entry["session"]
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		clean_payload = parser.clean_payload(response.payload)
		logg.debug("Probe on " + str(response.remote[0]) + " reported " + clean_payload + " i.e. MID:" + str(response.mid))
		payload = json.loads(clean_payload)
		info = None
		if cache_entry['command'].uri.startswith(terms.uri['6TP_CL']):
			info = payload
		elif cache_entry['command'].uri.startswith(terms.uri['6TP_SV']):
			info = payload
		cached_entry = self._decache(tk)
		self.communicate(self._report(node_id, cache_entry['command'].uri, info))
		self.communicate(self.reported(node_id, cache_entry['command'].uri, info))
		self._touch_session(cached_entry['command'], session_id)

	def _push_command(self, comm, session):
		if isinstance(comm, Command):
			self.cache[comm.id] = {'session': session, 'command': copy.copy(comm) } #id': comm.id, 'op': comm.op, 'to': comm.to, 'uri': comm.uri}
			if comm.payload:
				if isinstance(comm.payload, dict) and 'frame' in comm.payload:
					if comm.uri == terms.uri['6TP_SF']:
						comm.payload = {'ns': comm.payload['frame'].slots}
					elif comm.uri == terms.uri['6TP_CL']:
						comm.payload['fd'] = comm.payload['frame'].get_alias_id(comm.to)
						del comm.payload['frame']
			if not comm.callback:
				if comm.uri == terms.uri['RPL_NL']:
					comm.callback = self._observe_rpl_nodes
				elif comm.uri == terms.uri['RPL_OL']:
					comm.callback = self._observe_rpl_children
				elif comm.uri == terms.uri['6TP_SF']:
					comm.callback = self._receive_slotframe_id
				elif comm.op == 'post' and comm.uri == terms.uri['6TP_CL']:
					comm.callback = self._receive_cell_id
				elif comm.uri == terms.uri['6TP_CL']:
					comm.callback = self._receive_probe
				elif comm.uri == terms.uri['6TP_SM']:
					comm.callback = self._receive_probe
				elif comm.uri.startswith(terms.uri['6TP_SV']):
					comm.callback = self._receive_report
				elif comm.uri.startswith(terms.uri['6TP_CL']):
					comm.callback = self._receive_report
			logg.info("Sending to " + str(comm.to) + " >> " + comm.op + " " + comm.uri + " -- " + str(comm.payload))
			if comm.op == 'get':
				self.client.GET(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'observe':
				self.client.OBSERVE(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'post':
				self.client.POST(comm.to, comm.uri, parser.construct_payload(comm.payload), comm.id, comm.callback)
			elif comm.op == 'delete':
				self.client.DELETE(comm.to, comm.uri, comm.id, comm.callback)

	def _connect(self, child, parent, old_parent=None):
		if old_parent:
			logg.info(str(child) + ' rewired to ' + str(parent) + ' from ' + str(old_parent))
		else:
			logg.info(str(child) + ' wired to parent ' + str(parent))

		q = interface.BlockQueue()
		q.push(Command('observe', child, terms.uri['RPL_OL']))
		# TODO: commands.append(self.Command('post', child, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"})) # First step of statistics installation.
		q.block()
		return q

	def _disconnect(self, node_id):
		logg.info(str(node_id) + " was removed from the network")
		q = interface.BlockQueue()
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_links_of(node_id)
			for cell in deleted_cells:
				if cell.owner != node_id:
					q.push(Command('delete', cell.owner, terms.uri['6TP_CL']+'/'+str(cell.id)))
			del frame.fds[node_id]
		q.block()
		return q

	def _frame(self, who, frame, remote_fd, old_payload):
		logg.info(str(who) + " installed new " + frame.name + " frame with id=" + str(remote_fd))
		frame.set_alias_id(who, remote_fd)
		return None

	def _cell(self, who, slotoffs, channeloffs, frame, remote_cell_id, old_payload):
		logg.info(str(who) + " installed new cell (id=" + str(remote_cell_id) + ") in frame " + frame.name + " at slotoffset=" + str(slotoffs) + " and channel offset=" + str(channeloffs))
		return None

	def _probe(self, who, resource, info):
		logg.info('Probe at ' + str(who) + ' on ' + str(resource) + ' returned ' + str(info))
		return None

	def _report(self, who, resource, info):
		logg.info('Probe at ' + str(who) + ' on ' + str(resource) + ' reported ' + str(info))
		return None

	def communicate(self, assembly):
		"""
		Handle all the communication with the RICH network.
		"""
		if isinstance(assembly, interface.BlockQueue):
			self._create_session(assembly)
		elif isinstance(assembly, list):
			for i in assembly:
				if isinstance(i, interface.BlockQueue):
					self._create_session(i)

	def connected(self, child, parent, old_parent=None):
		pass

	def disconnected(self, node_id):
		pass

	def framed(self, who, local_name, remote_alias, old_payload):
		pass

	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		pass

	def probed(self, node, resource, value):
		pass

	def reported(self, node, resource, value):
		pass


class Scheduler(Reflector):

	def start(self):
		self.communicate(self.get_remote_children(self.root_id, True))
		self.client.start()

	def get_remote_frame(self, node, slotframe):  # TODO: observe (makes sense when distributed scheduling in place)
		assert isinstance(node, NodeID)
		assert isinstance(slotframe, Slotframe)
		raise exception.UnsupportedCase('GET command for slotframes is not supported')

	def set_remote_frames(self, node, slotframes):
		assert isinstance(node, NodeID)
		assert isinstance(slotframes, Slotframe) #TODO or isinstance(slotframes, array)
		q = interface.BlockQueue()
		for item in [slotframes] if isinstance(slotframes, Slotframe) else slotframes:
			q.push(Command('post', node, terms.uri['6TP_SF'], {'frame': item}))
		q.block()
		return q

	def get_remote_cell(self, node, cell=None):
		q = interface.BlockQueue()
		if cell is None:
			q.push(Command('get', node, terms.uri['6TP_CL']))
		elif isinstance(cell, (int, long)):
			q.push(Command('get', node, terms.uri['6TP_CL']+'/'+str(cell)))
		elif isinstance(cell, Cell) and cell.id:
			q.push(Command('get', node, terms.uri['6TP_CL']+'/'+str(cell.id)))
		else:
			return None
		q.block()
		return q

	def set_remote_link(self, slot, channel, slotframe, source, destination, target=None):
		assert isinstance(slotframe, Slotframe)
		assert channel <= 16
		assert slot < slotframe.slots
		assert isinstance(source, NodeID)
		assert destination is None or isinstance(destination, NodeID)

		q = interface.BlockQueue()

		if target and target != source and target not in self.dodag.get_children(source):
			return False

		found_tx = None
		found_rx = []
		for c in slotframe.cell_container:
			if c.slot == slot and c.channel == channel:
				if destination is not None and c.tx == source and c.rx == destination:
					if c.option == 1:
						found_tx = c.owner
					elif c.option == 2:
						found_rx.append(c.owner)
				elif destination is None:
					if c.tx == source and c.rx is None:
						if c.option == 9:
							found_tx = c.owner
						elif c.option == 10:
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
			comm = Command('post', c.owner, terms.uri['6TP_CL'], {'so':c.slot, 'co':c.channel, 'frame': slotframe, 'lo':c.option, 'lt':c.type})
			depth = self.dodag.get_node_depth(c.owner)
			if depth not in depth_groups:
				depth_groups[depth] = [comm]
			else:
				depth_groups[depth].append(comm)
		for j in sorted(depth_groups.keys(), reverse=True):
			for k in depth_groups[j]:
				q.push(k)
			q.block()

		return q

	def get_remote_children(self, node, observe=False):
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		q.push(Command('get' if not observe else 'observe', node, terms.uri['RPL_OL']))
		q.block()
		return q

	def get_remote_statistics(self, node, statistics=0, observe=False):
		q = interface.BlockQueue()
		if isinstance(statistics, (int, long)):
			q.push(Command('get' if not observe else 'observe', node, terms.uri['6TP_SV']+'/'+str(statistics)))
		else:
			return None
		q.block()
		return q

	def set_remote_statistics(self, node, definition):
		q = interface.BlockQueue()
		q.push(Command('post', node, terms.uri['6TP_SM'], definition))
		q.block()
		return q

	def disconnect_node(self, node):
		pass

	def conflict(self, slot, tx, rx, slotframe):
		assert isinstance(slotframe, Slotframe) and slotframe in self.frames.values()
		for item in slotframe.cell_container:
			if item.slot == slot:
				if item.rx == tx or (item.rx is None and (item.tx == self.dodag.get_parent(tx) or item.tx in self.dodag.get_children(tx))):
					return True
				elif (item.rx is not None and item.rx == rx) or \
						(item.rx is None and rx is not None and item.tx in self.dodag.get_neighbors(rx)) or \
						(item.rx is not None and rx is None and tx in self.dodag.get_neighbors(item.rx)) or \
						(rx is None and item.rx is None and not set(self.dodag.get_neighbors(tx)).isdisjoint(set(self.dodag.get_neighbors(item.tx)))):
					return True
		return False

	def interfere(self, slot, tx, rx, slotframe):
		assert isinstance(slotframe, Slotframe) and slotframe in self.frames.values()
		channels = []
		for item in slotframe.cell_container:
			if item.slot == slot and item.rx is not None and rx is not None and \
				item.rx not in self.dodag.get_neighbors(tx) and \
				rx not in self.dodag.get_neighbors(item.tx):
				channels.append(item.channel)
		return channels

	def schedule(self, tx, rx, slotframe):
		raise NotImplementedError()