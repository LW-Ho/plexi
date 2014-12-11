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
from util import parser
import json
from schedule.slotframe import Slotframe, Cell
from util import terms, exception
from txthings import coap
import logging
from util import logger
import string

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.INFO)


class Reflector(object):
	class command(object):
		def __init__(self, op, to, uri, payload=None, callback=None):
			self.op = op
			self.to = to
			self.uri = uri
			self.payload = payload
			self.callback = callback

	def __init__(self, net_name, lbr_ip, lbr_port, visualizer=False):
		self.root_id = NodeID(lbr_ip, lbr_port)
		self.client = LazyCommunicator(5)
		self.dodag = DoDAG(net_name, self.root_id, visualizer)
		self.frames = {}
		self.token = 0
		self.cache = {}
		self.token_buffer = []

	def start(self):
		self.commander(self.command('observe', self.root_id, terms.uri['RPL_NL']))
		self.commander(self.command('observe', self.root_id, terms.uri['RPL_OL']))
		self.commander(self.command('post', self.root_id, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"}))

	def _decache(self, token):
		if token:
			sent_msg = self.cache[token]
			if sent_msg['op'] != 'observe':
				del self.cache[token]

	def observe_rpl_nodes(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		sender = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(sender) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		#response.payload = response.payload.strip('{}')
		print "MID:", response.mid ,"FROM:", response.remote[0],"NODE LIST:",parser.clean_payload(response.payload) #<-----Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		self._decache(tk)
		for n in payload:
			node = NodeID(str(n))
			if self.dodag.attach_node(node):
				commands = self.popped(node)
				if commands:
					for comm in commands:
						self.commander(comm)

	def observe_rpl_children(self, response):
		print " ---> observe_rpl_children called <---"
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		parent_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(parent_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		print "MID:", response.mid ,"FROM:", response.remote[0],"CHILD LIST:",parser.clean_payload(response.payload) #<-----Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		observed_children = []
		for n in payload:
			observed_children.append(NodeID(str(n)))
		self._decache(tk)

		dodag_child_list = [child for (child, attributes) in self.dodag.graph[parent_id].items() if attributes['child'] != parent_id]
		removed_nodes = [item for item in dodag_child_list if item not in observed_children]
		for n in removed_nodes:
			if self.dodag.detach_node(n):
				commands = self.disconnected(n)
				if commands:
					for comm in commands:
						self.commander(comm)

		for k in observed_children:
			old_parent = self.dodag.get_parent(k)
			if self.dodag.attach_child(k, parent_id):
				commands = self.inherited(k, parent_id, old_parent)
				if commands:
					for comm in commands:
						self.commander(comm)

	def receive_slotframe_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		print "MID:", response.mid ,"FROM:", response.remote[0], parser.clean_payload(response.payload) #<---------------------------------Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		frame_alias = payload['fd']
		old_payload = self.cache[tk]['payload']
		frame_name = old_payload['frame']
		self._decache(tk)
		commands = self.framed(node_id, frame_name, frame_alias, old_payload)
		if commands:
			for comm in commands:
				self.commander(comm)

	def receive_cell_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		print "MID:", response.mid ,"FROM:", response.remote[0], parser.clean_payload(response.payload) #<---------------------------------Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		cell_cd = payload['cd']
		old_payload = self.cache[tk]['payload']
		frame_name = old_payload['frame']
		so = old_payload['so']
		co = old_payload['co']
		self._decache(tk)
		commands = self.celled(node_id, so, co, frame_name, cell_cd, old_payload)
		if commands:
			for comm in commands:
				self.commander(comm)

	def receive_cell_info(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		payload = json.loads(parser.clean_payload(response.payload))
		self._decache(tk)
		print(str(node_id) + ' - ' + str(payload))

	def receive_statistics_metrics_id(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		print "MID:", response.mid ,"FROM:", response.remote[0], parser.clean_payload(response.payload) #<---------------------------------Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		metric_id = payload[terms.keys['SM_ID']]
		#old_payload = self.cache[tk]['payload']
		#frame_name = old_payload['frame']
		self._decache(tk)
		commands = self.stm_id(node_id, metric_id)
		if commands:
			for comm in commands:
				self.commander(comm)

	def receive_statistics_metrics_value(self, response):
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			self._decache(tk)
			raise exception.UnsupportedCase(tmp)
		print "MID:", response.mid ,"FROM:", response.remote[0], parser.clean_payload(response.payload) #<---------------------------------Print for debugging
		payload = json.loads(parser.clean_payload(response.payload))
		#metric_values = payload
		#old_payload = self.cache[tk]['payload']
		#frame_name = old_payload['frame']
		self._decache(tk)
		commands = self.stm_value(node_id, payload)
		if commands:
			for comm in commands:
				self.commander(comm)

	def commander(self, comm):
		if isinstance(comm, self.command):
			self.token += 1
			#if [x for x in self.cache.values() if x["to"]==comm.to and x["op"]==comm.op and x["uri"]==comm.uri and x["payload"]==comm.payload]:
			#	print("bingo")
			self.cache[self.token] = {'op': comm.op, 'to': comm.to, 'uri': comm.uri}
			if comm.payload:
				self.cache[self.token]['payload'] = comm.payload.copy()
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
				elif comm.uri == terms.uri['6TP_SM']:
					comm.callback = self.receive_statistics_metrics_id
				elif comm.uri.startswith(terms.uri['6TP_SV']+"/0"):
					comm.callback = self.receive_statistics_metrics_value
				elif comm.uri.startswith(terms.uri['6TP_CL']):
					comm.callback = self.receive_cell_info
			print comm.op,"TO:",comm.to,"URI:",comm.uri,"PAYLOAD:",comm.payload #<----------Print for debugging
			if comm.op == 'get':
				self.client.GET(comm.to, comm.uri, self.token, comm.callback)
			elif comm.op == 'observe':
				self.client.OBSERVE(comm.to, comm.uri, self.token, comm.callback)
			elif comm.op == 'post':
				self.client.POST(comm.to, comm.uri, parser.construct_payload(comm.payload), self.token, comm.callback)
			elif comm.op == 'delete':
				self.client.DELETE(comm.to, comm.uri, self.token, comm.callback)

	def popped(self, node):
		pass

	def inherited(self, child, parent, old_parent=None):
		pass

	def framed(self, who, local_name, remote_alias, old_payload):
		pass

	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		pass

	def stm_id(self, node_id, metric_id):
		pass

	def stm_value(self, node_id, metric_values):
		pass

	def updated(self):
		pass

	def disconnected(self, node_id):
		pass

class Scheduler(Reflector):
	def __init__(self, net_name, lbr_ip, lbr_port, visualizer):
		super(Scheduler, self).__init__(net_name, lbr_ip, lbr_port, visualizer)
		self.slot_counter = 2
		self.channel_counter = 0
		self.b_slot_counter = 2
		self.pairs = []
		self.commands_waiting = []

	def start(self):
		super(Scheduler, self).start()
		f1 = Slotframe("Broadcast-Frame", 201) #Changed values for interaction testing
		f2 = Slotframe("Unicast-Frame", 101)
		self.frames[f1.name] = f1
		self.frames[f2.name] = f2
		self.rb_flag = 0
		for k in self.frames.keys():
			self.commander(self.command('post', self.root_id, terms.uri['6TP_SF'], {'frame': k}))
		#	self.frames[k].setAliasID(self.root_id, None)
		cb_root = Cell(1, 0, self.root_id, None, None, 1, 10)
		self.frames['Broadcast-Frame'].cell_container.append(cb_root)
		self.client.start()     # this has to be the last line of the start function ... ALWAYS
		# print cb_root.__dict__
		# print " POST | 6t/6/cl | {\"so\": cb.slot, \"co\": cb.channel, \"fd\": cb.slotframe_id, \"lo\": cb.link_option, \"lt\": cb.link_type} "

	def popped(self, node):
		logg.info(str(node) + ' popped up')

	def inherited(self, child, parent, old_parent=None):
		print " ---> inherited called <---"
		if old_parent:
			logg.info(str(child) + ' rewired to ' + str(parent) + ' from ' + str(old_parent))
		else:
			logg.info(str(child) + ' wired to parent ' + str(parent))

		commands = []

		commands.append(self.command('observe', child, terms.uri['RPL_OL']))
		commands.append(self.command('post', child, terms.uri['6TP_SM'], {"mt":"[\"PRR\",\"RSSI\"]"})) # First step of statistics installation.

		old_child_list_full = self.dodag.graph.neighbors(parent)
		for item in old_child_list_full:
			old_child_list = []
			tmp = item.eui_64_ip
			old_child_list.append(tmp)

		print 'children list is:', old_child_list

		#new_child_list = response.payload
		for k in self.frames.keys():
			commands.append(self.command('post', child, terms.uri['6TP_SF'], {'frame': k}))

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


	def disconnected(self, node_id):
		commands = []
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_cell(node_id)
			for cell in deleted_cells:
				# delete command
				to = cell.tx_node if cell.link_option == 1 else cell.rx_node
				commands.append(self.command('delete', NodeID(to), terms.uri['6TP_CL']+'/'+str(cell.cell_id)))

		return commands

	def framed(self, who, local_name, remote_alias, old_payload):
		self.frames[local_name].setAliasID(who, remote_alias)
		commands = []

		parent = NodeID()
		child = NodeID()

		for pair in self.pairs:
			if pair[0].ip == who.ip:
				child = pair[1]
				parent = pair[0]
			elif pair[1].ip == who.ip:
				parent = pair[0]
				child = pair[1]

		if who == self.root_id and self.rb_flag == 0 and local_name == "Broadcast-Frame":
			for item in self.frames[local_name].cell_container:
				if item.link_option == 10 and item.tx_node == who:
					item.slotframe_id = self.frames[local_name].fds[who]

				if item.link_option == 9 and item.rx_node == who:
					item.slotframe_id = self.frames[local_name].fds[self.root_id]

			for item in self.frames[local_name].cell_container:
				if item.link_option == 10 and item.tx_node == who and item.slotframe_id != None:
					commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))

			for item in self.frames[local_name].cell_container:
				if item.link_option == 9 and item.rx_node == who and item.slotframe_id != None:
					#if [x for x in commands if x.to==item.rx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#   print("bingo")
					commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))

			#self.rb_flag = 1

		#elif who == self.root_id and self.rb_flag == 1:
		#	for item in self.frames[local_name].cell_container:
		#		if item.slotframe_id != None and item.rx_node == self.root_id:
		#			item.slotframe_id = self.frames[local_name].fds[who]
		#			commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))

		else:
			#pass
			for item in self.frames[local_name].cell_container:

				if item.slotframe_id == None:
					if item.link_option == 1 and item.tx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

					elif item.link_option == 2 and item.rx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

					elif item.link_option == 10 and item.tx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

					elif item.link_option == 9 and item.rx_node == who:
						item.slotframe_id = self.frames[local_name].fds[who]

					#elif item.link_option == 9 and item.rx_node == self.root_id:
					#	item.slotframe_id = self.frames[local_name].fds[self.root_id]

					else:
						#Broadcasts.
						pass

			for item in self.frames[local_name].cell_container:
				#item = self.frames[local_name].cell_container[i]


				#if item.slotframe_id != None:
				if item.link_option == 2 and item.rx_node == who and item.slotframe_id != None:
					#if [x for x in commands if x.to==item.rx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#	print("bingo")
					commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}))
				elif item.link_option == 1 and item.tx_node == who and item.slotframe_id != None and item.rx_node == parent:
					#if [x for x in commands if x.to==item.tx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#	print("bingo")
					commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt': item.link_type, 'na': item.rx_node.eui_64_ip}))
					#print item.rx_node.eui_64_ip, type(item.rx_node.eui_64_ip)
				elif item.link_option == 1 and item.tx_node == who and item.slotframe_id != None:# and item.rx_node == child:
					#if [x for x in commands if x.to==item.tx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#	print("bingo")
					self.commands_waiting.append(self.command('post', item.tx_node, terms.uri['6TP_CL'],{'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt': item.link_type, 'na': item.rx_node.eui_64_ip}))
					#print item.rx_node.eui_64_ip, type(item.rx_node.eui_64_ip)
				elif item.link_option == 10 and item.tx_node == who and item.slotframe_id != None:
					#if [x for x in commands if x.to==item.tx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#	print("bingo")
					commands.append(self.command('post', item.tx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))
				elif item.link_option == 9 and item.rx_node == who and item.rx_node != self.root_id and item.slotframe_id != None:
					#if [x for x in commands if x.to==item.rx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
					#   print("bingo")
					commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))
				#elif item.link_option == 9 and item.rx_node == self.root_id and item.slotframe_id != None:
					#if [x for x in commands if x.to==item.rx_node and x.op=='post' and x.uri==terms.uri['6TP_CL'] and x.payload=={'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id, 'frame': local_name, 'lo': item.link_option, 'lt':item.link_type}]:
				#	print("bingo")
				#	commands.append(self.command('post', item.rx_node, terms.uri['6TP_CL'], {'so':item.slot, 'co':item.channel, 'fd':item.slotframe_id,'frame': local_name, 'lo':item.link_option, 'lt':item.link_type}))


		return commands

#		return [self.command('post', who, terms.uri['6TP_CL'],{'so': 1, 'co': 2, 'fd': remote_alias, 'frame': local_name, 'op': 3, 'ct': 4})]
		# create a broadcast cell for the root, append the created cell at broadcast_cell_container and post the cell to the root's slotframe


	def celled(self, who, slotoffs, channeloffs, frame_name, remote_cell_id, old_payload):
		commands = []

		for item in self.commands_waiting:
			if item.payload['na'] == who.eui_64_ip:
				commands.append(item)
				self.commands_waiting.remove(item)

		#print old_payload
		# TODO: self.frames[frame_name].cell(so, co, node_id).id = cell_cd
		for item in self.frames[frame_name].cell_container:
			if item.slot == slotoffs and item.channel == channeloffs and item.link_type == old_payload["lo"]:
				item.cell_id = remote_cell_id
				if item.rx_node:
					self.dodag.update_link(item.tx_node, item.rx_node, 'SLT', '++')
				else:
					self.dodag.update_node(item.tx_node, 'SLT', '++')

		return commands

	def schedule_unicast(self, tx_node, rx_node, sf_id):

		ct = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, sf_id, 0,1)
		cr = Cell(self.slot_counter, self.channel_counter, tx_node, rx_node, sf_id, 0,2)

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

	def stm_id(self, node_id, metric_id):
		commands = []

		id_appended_uri = terms.uri['6TP_SV'] + "/" + str(metric_id)
		commands.append(self.command('observe', node_id, id_appended_uri))

		return commands

	def stm_value(self, node_id, payload):
		for item in payload:
			for key in item.keys():
				if isinstance(key, unicode):
					key = key.encode('utf-8')
				for node in self.dodag.graph.nodes():
					if node.eui_64_ip == key:
						key_id = node
				if self.dodag.graph.has_edge(node_id, key_id): # or self.dodag.graph.has_edge(key, node_id.eui_64_ip):
					self.dodag.graph[node_id][key_id]["statistics"] = item[key]
					print node_id.eui_64_ip + " =",self.dodag.graph.edge[node_id][key_id]




