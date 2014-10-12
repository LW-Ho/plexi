from endpoint.client import RichClient
from schedule.graph import DoDAG
from resource.rpl import NodeID
import json
from schedule.slotframe import Slotframe, Cell
from util import terms, exception
from coapthon2 import defines


class Reflector(object):
	class command(object):
		def __init__(self, op, to, uri, payload=None, callback=None):
			self.op = op
			self.to = to
			self.uri = uri
			self.payload = payload
			self.callback = callback

	def __init__(self, net_name, lbr_ip, lbr_port, forward=False):
		self.root_id = NodeID(lbr_ip, lbr_port)
		self.client = RichClient(forward)
		self.dodag = DoDAG(net_name, self.root_id, True)
		self.frames = {}
		self.token = 0
		self.cache = {}
		self.token_buffer = []

	def start(self):
		self.commander(self.command('observe', self.root_id, terms.uri['RPL_NL']), True)
		self.commander(self.command('observe', self.root_id, terms.uri['RPL_OL']), True)

	def _decache(self, token):
		if token:
			sent_msg = self.cache[token]
			if sent_msg['op'] != 'observe':
				del self.cache[token]

	def observe_rpl_nodes(self, response, kwargs):
		if str(response.token) not in self.cache:
			return
		sender = NodeID(kwargs['from'][0], kwargs['from'][1])
		if response.code != defines.responses['CONTENT']:
			tmp = str(sender) + ' returned a ' + defines.inv_responses[response.code] + '\n\tRequest: ' + str(self.cache[response.token])
			self._decache(response.token)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(response.payload)
		self._decache(response.token)
		for n in payload:
			node = NodeID(str(n[0]), int(n[1]))
			if self.dodag.attach_node(node):
				commands = self.popped(node)
				if commands:
					for comm in commands:
						self.commander(comm)

	def observe_rpl_children(self, response, kwargs):
		if str(response.token) not in self.cache:
			return
		parent_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		if response.code != defines.responses['CONTENT']:
			tmp = str(parent_id) + ' returned a ' + defines.inv_responses[response.code] + '\n\tRequest: ' + str(self.cache[response.token])
			self._decache(response.token)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(response.payload)
		self._decache(response.token)
		for n in payload:
			child_id = NodeID(str(n[0]), int(n[1]))
			old_parent = self.dodag.get_parent(child_id)
			if self.dodag.attach_child(child_id, parent_id):
				commands = self.inherited(child_id, parent_id, old_parent)
				if commands:
					for comm in commands:
						self.commander(comm)

	def receive_slotframe_id(self, response, kwargs):
		if str(response.token) not in self.cache:
			return
		node_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		if response.code != defines.responses['CREATED']:
			tmp = str(node_id) + ' returned a ' + defines.inv_responses[response.code] + '\n\tRequest: ' + str(self.cache[response.token])
			self._decache(response.token)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(response.payload)
		frame_alias = payload['fd']
		old_payload = self.cache[str(response.token)]['payload']
		frame_name = old_payload['frame']
		self._decache(response.token)
		commands = self.framed(node_id, frame_name, frame_alias, old_payload)
		if commands:
			for comm in commands:
				self.commander(comm)

	def receive_cell_id(self, response, kwargs):
		if str(response.token) not in self.cache:
			return
		node_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		if response.code != defines.responses['CREATED']:
			tmp = str(node_id) + ' returned a ' + defines.inv_responses[response.code] + '\n\tRequest: ' + str(self.cache[response.token])
			self._decache(response.token)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(response.payload)
		cell_cd = payload['cd']
		old_payload = self.cache[str(response.token)]['payload']
		frame_name = old_payload['frame']
		so = old_payload['so']
		co = old_payload['co']
		self._decache(response.token)
		commands = self.celled(node_id, so, co, frame_name, cell_cd, old_payload)
		if commands:
			for comm in commands:
				self.commander(comm)

	def receive_cell_info(self, response, kwargs):
		if str(response.token) not in self.cache:
			return
		node_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		if response.code != defines.responses['CONTENT']:
			tmp = str(node_id) + ' returned a ' + defines.inv_responses[response.code] + '\n\tRequest: ' + str(self.cache[response.token])
			self._decache(response.token)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(response.payload)
		self._decache(response.token)
		print(str(node_id) + ' - ' + str(payload))

	def commander(self, comm, defer=False):
		if isinstance(comm, self.command):
			self.token += 1
			self.token_buffer.append(self.token)
			self.cache[str(self.token)] = {'op': comm.op, 'to': comm.to, 'uri': comm.uri}
			if comm.payload:
				self.cache[str(self.token)]['payload'] = comm.payload.copy()
				if isinstance(comm.payload, dict) and 'frame' in comm.payload:
					if comm.uri == terms.uri['6TP_SF']:
						comm.payload = {'ns': self.frames[comm.payload['frame']].slots}
					elif comm.uri == terms.uri['6TP_CL']:
						del comm.payload['frame']
			if not comm.callback:
				if comm.uri == terms.uri['RPL_NL']:
					comm.callback = self.observe_rpl_nodes
				elif comm.uri == terms.uri['RPL_OL']:
					comm.callback = self.observe_rpl_children
				elif comm.uri == terms.uri['6TP_SF']:
					comm.callback = self.receive_slotframe_id
				elif comm.uri == terms.uri['6TP_CL']:
					comm.callback = self.receive_cell_id
				elif comm.uri.startswith(terms.uri['6TP_CL']):
					comm.callback = self.receive_cell_info
			if comm.op == 'get':
				self.client.GET(comm.to, comm.uri, str(self.token), comm.callback, defer)
			elif comm.op == 'observe':
				self.client.OBSERVE(comm.to, comm.uri, str(self.token), comm.callback, defer)
			elif comm.op == 'post':
				self.client.POST(comm.to, comm.uri, json.dumps(comm.payload), str(self.token), comm.callback, defer)
			elif comm.op == 'delete':
				self.client.DELETE(comm.to, comm.uri, str(self.token), comm.callback, defer)

	def popped(self, node):
		pass

	def inherited(self, child, parent, old_parent=None):
		pass

	def framed(self, who, local_name, remote_alias, old_payload):
		pass

	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		pass


class Scheduler(Reflector):
	def __init__(self, net_name, lbr_ip, lbr_port, forward=False):
		super(Scheduler, self).__init__(net_name, lbr_ip, lbr_port, forward)
		self.slot_counter = 0
		self.channel_counter = 0
		self.b_slot_counter = 2

	def start(self):
		super(Scheduler, self).start()
		f1 = Slotframe("Broadcast-Frame", 202)
		f2 = Slotframe("Unicast-Frame", 101)
		self.frames[f1.name] = f1
		self.frames[f2.name] = f2
		counter = 0
		self.rb_flag = 0
		for k in self.frames.keys():
			if counter < len(self.frames)-1:
				self.commander(self.command('post', self.root_id, terms.uri['6TP_SF'], {'frame': k}), True)
			else:
				self.commander(self.command('post', self.root_id, terms.uri['6TP_SF'], {'frame': k}))
			counter += 1
		# # schedule the root at a broadcast cell --> (so: 1, co: 0)
		# cb_root = Cell(1, 0, self.root_id, None, self.frames['Broadcast-Frame'].name, 1, 10)
		# self.frames['Broadcast-Frame'].cell_container.append(cb_root)
		# print cb_root.__dict__
		# print " POST | 6t/6/cl | {\"so\": cb.slot, \"co\": cb.channel, \"fd\": cb.slotframe_id, \"lo\": cb.link_option, \"lt\": cb.link_type} "

	def popped(self, node):
		pass

	def inherited(self, child, parent, old_parent=None):
		if old_parent:
			print(str(child) + ' rewired to ' + str(parent) + ' from ' + str(old_parent))
		else:
			print(str(child) + ' wired to parent ' + str(parent))

		commands = []
		commands.append(self.command('observe', child, terms.uri['RPL_OL']))

		for k in self.frames.keys():
			commands.append(self.command('post', child, terms.uri['6TP_SF'], {'frame': k})) # Scheduling should start when we receive the frame ids.Move the post actions to framed.Leave schduling here.

		c_flag = False

		if self.b_slot_counter >= self.frames["Broadcast-Frame"].slots:
					print("out of broadcast cells")
					return False

		if self.frames["Broadcast-Frame"].fds[parent] == None:
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

		return commands


	def framed(self, who, local_name, remote_alias, old_payload):
		self.frames[local_name].setAliasID(who, remote_alias)
		commands = []

		# create the b_cell(1,0) for root to start broadcasting in the start
		if who == self.root_id and self.rb_flag == 0:
			cb_root = Cell(1, 0, who, None, self.frames[local_name].fds[who], 1, 10)
			self.frames["Broadcast-Frame"].cell_container.append(cb_root)
			commands.append(self.command('post', who, terms.uri['6TP_CL'], {'so':cb_root.slot, 'co':cb_root.channel, 'fd':cb_root.slotframe_id,'frame':local_name, 'lo':cb_root.link_option, 'lt':cb_root.link_type}))
			self.rb_flag = 1

		else:
			for item in self.frames[local_name].cell_container:

				if item.slotframe_id == None:
					if item.link_option == 1 and item.tx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

						#commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}))
						#for item2 in self.frames[local_name].cell_container:
						#	if item.slot == item2.slot and item.channel == item2.channel and item2.link_option == 2:
						#		commands.append(self.command('post',item2.rx_node, terms.uri['6TP_CL'],{'so':item2.slot, 'co':item2.channel, 'fd':item2.slotframe_id, 'frame': local_name, 'lo': item2.link_option, 'lt':item2.link_type}))

					elif item.link_option == 2 and item.rx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

						#commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}))
						#for item2 in self.frames[local_name].cell_container:
						#	if item.slot == item2.slot and item.channel == item2.channel and item2.link_option == 1:
						#		commands.append(self.command('post',item2.tx_node, terms.uri['6TP_CL'],{'so':item2.slot, 'co':item2.channel, 'fd':item2.slotframe_id, 'frame': local_name, 'lo': item2.link_option, 'lt':item2.link_type}))

					elif item.link_option == 10 and item.tx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

						#commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'lo':item.link_option, 'lt':item.link_type}))
						#for item2 in self.frames[local_name].cell_container:
						#	if item.slot == item2.slot and item.channel == item2.channel and item2.link_option == 9:
						#		commands.append(self.command('post', item2.rx_node, terms.uri['6TP_CL'], {'so':item2.slot, 'co':item2.channel, 'fd':item2.slotframe_id, 'frame': local_name, 'lo': item2.link_option, 'lt':item2.link_type}))
								#for item3 in self.frames[local_name].cell_container:

					elif item.link_option == 9 and item.rx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

					else:
						#Broadcasts.
						pass

				for item in self.frames[local_name].cell_container:
					if item.slotframe_id != None:
						if item.link_option == 1 and item.tx_node == who:
							commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}))
						elif item.link_option == 2 and item.rx_node == who:
							commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}))
						elif item.link_option == 10 and item.tx_node == who:
							commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))
						elif item.link_option == 9 and item.rx_node == who:
							commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))


		return commands

#		return [self.command('post', who, terms.uri['6TP_CL'],{'so': 1, 'co': 2, 'fd': remote_alias, 'frame': local_name, 'op': 3, 'ct': 4})]
		# create a broadcast cell for the root, append the created cell at broadcast_cell_container and post the cell to the root's slotframe


	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		# TODO: self.frames[frame_name].cell(so, co, node_id).id = cell_cd
		for item in self.frames[frame_name].cell_container:
			if item.slot == slotoffs and item.channel == channeloffs and item.link_type == old_payload["lo"]:
				item.cell_id = remote_cell_id

	def schedule_unicast(self, tx_node, rx_node, sf_id):

		ct = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, sf_id, 0,1)
		cr = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, sf_id, 0,2)

		#print ct.__dict__
		#print cr.__dict__
		#self.frames["Unicast-Frame"].fds[tx_node]

		self.frames["Unicast-Frame"].cell_container.append(ct)
		self.frames["Unicast-Frame"].cell_container.append(cr)

		self.channel_counter = self.channel_counter + 1
		if self.channel_counter == 17 :
			print("ERROR: We are out of channels!")
			return False

		#self.commands.append(self.command('post',tx_node ,terms.uri['6TP_CL'],{'so':ct.slot, 'co':ct.channel, 'fd':ct.slotframe_id, 'lo':ct.link_option, 'lt':ct.link_type}))
		#self.commands.append(self.command('post',rx_node ,terms.uri['6TP_CL'],{'so':cr.slot, 'co':cr.channel, 'fd':cr.slotframe_id, 'lo':cr.link_option, 'lt':cr.link_type}))

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


		# BroadCast Cell is being posted
		#print cb.__dict__
		#commands.append(self.command('post',tx_node ,terms.uri['6TP_CL'],{'so':cb_brd.slot, 'co':cb_brd.channel, 'fd':cb_brd.slotframe_id, 'lo':cb_brd.link_option, 'lt':cb_brd.link_type}))

		#parent = self.dodag.get_parent(tx_node)

		cb_nb = Cell(self.b_slot_counter, 0, None, self.dodag.get_parent(tx_node), sf_id, 1, 9)
		self.frames["Broadcast-Frame"].cell_container.append(cb_nb)
		for item in self.frames["Broadcast-Frame"].cell_container:
			#print self.dodag.get_parent(tx_node), type(self.dodag.get_parent(tx_node))
			#print item.tx_node, type(item.tx_node)
			if item.link_option != 7 and item.tx_node and item.tx_node == self.dodag.get_parent(tx_node):
				cb_nb2 = Cell(item.slot, 0, None, tx_node, None, 1, 9)
				self.frames["Broadcast-Frame"].cell_container.append(cb_nb2)


		#for nb in self.dodag.graph.neighbors(tx_node):
		#	cb_nb = Cell(self.b_slot_counter, 0, None, nb, sf_id, 1, 9)
		#	self.frames["Broadcast-Frame"].cell_container.append(cb_nb)
		#	for item in self.frames["Broadcast-Frame"].cell_container:
		#		if item.tx_node == nb:
		#			cb_nb2 = Cell(item.slot, 0, None, tx_node, None, 1, 9)
		#			self.frames["Broadcast-Frame"].cell_container.append(cb_nb2)

		self.b_slot_counter = self.b_slot_counter + 1

			#self.commands.append(self.command('post', nb, terms.uri['6TP_CL'], {'so':cb_nb.slot, 'co':cb_nb.channel, 'fd':cb_nb.slotframe_id, 'lo':cb_nb.link_option, 'lt':cb_nb.link_type}))


