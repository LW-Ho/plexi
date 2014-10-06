from endpoint.client import RichClient
from graph import DoDAG
from resource.rpl import NodeID
import json
from util.exception import FormatError


class Scheduler(object):
	def __init__(self, net_name, lbr_ip, lbr_port, forward=False):
		self.root_id = NodeID(lbr_ip, lbr_port)
		self.client = RichClient(forward)
		self.dodag = DoDAG(net_name, self.root_id, True)
		self.token = 1

	def start(self):
		self.client.OBSERVE(self.root_id, 'rpl/node/', str(self.token), self.observe_rpl_nodes)

	def observe_rpl_nodes(self, response, kwargs):
		payload = json.loads(response.payload)
		for n in payload:
			node = NodeID(str(n[0]), int(n[1]))
			if self.dodag.attach_node(node):
				#self.client.OBSERVE(node, 'rpl/p/', str(++self.token), self.observe_rpl_parents)
				self.client.OBSERVE(node, 'rpl/p/', str(++self.token), self.observe_rpl_children)

	def observe_rpl_parents(self, response, kwargs):
		child_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		payload = json.loads(response.payload)
		if len(payload) > 1:
			raise FormatError(str(response.payload))
		for n in payload:
			parent_id = NodeID(str(n[0]), int(n[1]))
			self.dodag.attach_child(child_id, parent_id)

	def observe_rpl_children(self, response, kwargs):
		parent_id = NodeID(kwargs['from'][0], kwargs['from'][1])
		payload = json.loads(response.payload)
		for n in payload:
			child_id = NodeID(str(n[0]), int(n[1]))
			self.dodag.attach_parent(parent_id, child_id)

	def schedule(self):
		pass