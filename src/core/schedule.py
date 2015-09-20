__author__ = "Dimitris Sarakiotis, Ilker Oztelcan, George Exarchakos, Frank Boerman"
__email__ = "d.sarakiotis@tue.nl, i.oztelcan@tue.nl, g.exarchakos@tue.nl, f.j.l.boerman@student.tue.nl"
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
import datetime
from twisted.internet import task
import socket
import time
from sets import Set
import re

logg = logging.getLogger('RiSCHER')
logg.setLevel(logging.DEBUG)


class Reflector(object):
	"""
	Handle all the communication with the RICH network in a concurrent way.

	Implements a callback-model to send operations to network nodes and trigger the appropriate callback upon replies.
	Maintains the proper sequence of messages to be sent to each node separately. For instance, it makes sure a cell is not
	POSTed at a node before that node has returned the id of the frame the cell belongs to; instead, the message is cached.

	Every communication between the :class:`Reflector` and a node in the network is split in sessions. Each session is independent
	from any other session and runs in parallel to others. That allows concurrent communication between the scheduler and
	any node. The parallel sessions the :class:`Reflector` is engaged with, can be with the same or different nodes.

	Each session defines a sequence of blocks of commands destined to various nodes. Commands in the same block can be transmitted
	simultaneously. All commands of a block need to have replied before the next block is executed. Users of :class:`Reflector`
	should define those sessions with their blocks externally.

	Besides the user-defined sessions, this class maintains the RPL DoDAG by installing a children observer to every node
	of the network.

	The class provides a callback system for the following operations and resources:

	- GET & OBSERVE on RPL children of a node: the returned list of children is compared against current RPL DoDAG to determing (dis)connected nodes
	- POST a new slotframe: sets a frame of specific size (num. of slots) to a node. A callback is triggered upon received slotframe ID
	- GET, POST & DELETE a cell: installs/deletes a new cell to a node. A callback is triggered upon received cell ID.
	- GET, OBSERVE & POST a statistics resource: defines a new statistics resource with POST and can read its value with GET or OBSERVE. A call back is triggered upon receive resource ID or value.
	- GET, OBSERVE, POST & DELETE any user-defined resource
	"""

	def __init__(self, net_name, lbr_ip, lbr_port, prefix, visualizer=None):
		"""
		Configure :class:`Reflector` with a network name and the EUI64 address and port of the border router. Initialize
		the DoDAG tree with a single node, the border router.

		:param net_name: a name for the network this scheduler handles
		:type net_name: str
		:param lbr_ip: EUI64 address of the border router
		:type lbr_ip: str
		:param lbr_port: the CoAP port of the border router e.g. 5684
		:type lbr_port: int
		:param prefix: network prefix prepended to the EUI64 address e.g. aaaa
		:type prefix:str
		"""
		NodeID.prefix = prefix
		self.root_id = NodeID(lbr_ip, lbr_port)
		logg.info("scheduler interface started with LBR=" + str(self.root_id))
		self.client = LazyCommunicator(5)
		self.dodag = DoDAG(net_name, self.root_id, visualizer)
		self.cache = {}
		self.sessions = {}
		self.start_commands = []
		self.count_sessions = 0
		#nodes who are temporary lost from the network are stored in here
		#this could be either a rewiring or a true disconnect
		#key: NodeID value: time left on lost list
		self.lost_children = {}
		#ammount of time a lost node can be on this list until truely disconnecting, in seconds
		self.time_until_dissconnect = 30
		#dictionary with frames as key and lists of blacklisted cells as value. blacklisted cell in format: [channeloff, slotoff]
		self.blacklisted = {}
		#dictionary with all defined frames
		self.frames = {}
		#frame which needs to be latered when there is a rewire happening
		self.rewireframe = ""

		if visualizer is not None:
			logg.info("connecting to visualizer server")
			try:
				HOST = visualizer
				PORT = 600
				self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket.connect((HOST, PORT))
				self.socket.sendall(lbr_ip)
			except:
				logg.critical("could not reach the visualizer server! (are you sure its online and specified correct ip?)")
		else:
			self.socket = None


	def _start(self):
		"""
		registers the looping call for the :func:`_TimeTick` into the twisted library

		:return None
		"""
		l = task.LoopingCall(self._TimeTick)
		l.start(1.0)
		comms = self.start_commands
		self.start_commands = None
		for comm in reversed(comms):
			self.communicate(comm)

		self.client.start()


	def _decache(self, token):
		"""
		Remove and return the cache entry (= a command) with the given token (= id)

		:param token: the token/id of the command to be detected and removed
		:type token: int
		:return: the command with the specified token
		:rtype: Command, or None if not found
		"""

		entry = None
		if token is not None:
			entry = self.cache[token]
			if entry['command'].op != 'observe':
				del self.cache[token]
		return entry

	def _create_session(self, assembly):
		"""
		Creates and initiates a session given a BlockQueue. The session is registered to this object and all the commands
		of its first block are sent to their destinations.

		:param assembly: a stack of blocks of commands to be sent to the network nodes
		:type assembly: BlockQueue
		"""
		if assembly and len(assembly) > 0:
			self.count_sessions += 1
			# Register the BlockQueue to the list of sessions
			self.sessions[self.count_sessions] = assembly
			# Iterate over the commands of the first block of the new session
			comm = self.sessions[self.count_sessions].pop()
			while comm:
				# Transmit each command
				self._push_command(comm, self.count_sessions)
				if self.count_sessions not in self.sessions or len(self.sessions[self.count_sessions]) == 0:
					break
				comm = self.sessions[self.count_sessions].pop()

	def _TimeTick(self):
		"""
		This function is ran every second and decreases the value of the lost_children dictionary item with as key the
		mac address of the lost child.
		When this value is 0 the disconnection procedure of this node is started. Also :func:`_DumpGraph` is called to
		create a snapshot of the system after disconnection

		:return: None
		"""
		#iterate throught the lost children list and subtract 1 from each entry
		for key, value in self.lost_children.iteritems():
			#if time is over pop this item and disconnect it, otherwise just decrement
			if value == 0:
				#save its children
				children = self.dodag.get_children(key)
				#disconnect the node and execute commands for this disconnect
				if self.dodag.detach_node(key):
					self._DumpGraph()
					self.communicate(self._disconnect(key, children))
					self.communicate(self.disconnected(key))
				self.lost_children.pop(key,0)
				#because the dict changed, break here, other disconnections are thus done with 1 second delay
				break
			else:
				self.lost_children[key] = value - 1

	def _touch_session(self, achieved_comm, session_id):
		"""
		Remove a given command from a session. Send subsequent block of commands if the given command was the last pending
		command of the current block of the session.

		:param achieved_comm: command that needs to be deleted from the session
		:type achieved_comm: Command
		:param session_id: identifier of the session from which the commands needs to be deleted
		:type session_id: int
		"""

		if session_id in self.sessions:
			# Get the BlockQueue corresponding to the session_id
			session = self.sessions[session_id]
			# Unblock the achieved_comm from the current block of session. Open up the next block if current is finished
			session.unblock(achieved_comm)
			# if more commands are in the session, transmit them to their destinations
			if not session.finished():
				# Note that pop returns None if the current block has still pending replies of commands
				comm = session.pop()
				while comm:
					self._push_command(comm, session_id)
					comm = session.pop()
			else:
				del self.sessions[session_id]

	def _observe_rpl_children(self, payload, parent_id):
		"""
		handles the parsing of received children list resource (part of the dodag resource). If a node is lost it is put
		on the lost child list, if a node has appeared the connection procedure is started.

		:param payload: the children list
		:type payload: list
		:param parent_id: the id of the node which transmitted this child list
		:type parent_id: :class:`node.NodeID`
		:raises: UnsupportedCase

		"""

		# Build a list of fetched children from the payload
		observed_children = []
		for n in payload:
			observed_children.append(NodeID(str(n)))
		# # Find, remove and return the cache entry of the command that triggered this response
		# cached_entry = self._decache(tk)
		dodag_child_list = self.dodag.get_children(parent_id)

		# Detect the children that were deleted, those that are in the local DoDAG but are not in the fetched children list
		removed_nodes = [item for item in dodag_child_list if item not in observed_children]
		# Iterate over all deleted children and detach them from the local DoDAG.
		# If detachment successful,
		#  build a session (BlockQueue) to remove the related cells from affected neighbors
		#  let user-defined function add a new session if needed
		#  TODO: what if the user would like to have a block queue only after the related cells are deleted?
		for rn in removed_nodes:
			logg.debug("child is lost: " + str(rn))
			if rn not in self.lost_children: #do not reset the timer if it is already there for a reason
				self.lost_children[rn] = self.time_until_dissconnect


		# Iterate over all fetched children and try to attach them to the local DoDAG if they are not attached already
		# if they are already attached than the change in children list is due to a rewiring
		# If attachment successful,
		#  build and send a BlockQueue session to install a children list observer to the new node
		#  let user-defined function add a new session if needed
		for k in observed_children:
			#if a
			if not self.dodag.check_node(k):
				old_parent = self.dodag.get_parent(k)
				if self.dodag.attach_child(k, parent_id):
					self._DumpGraph()
					self.communicate(self._connect(k, parent_id, old_parent))
					self.communicate(self.connected(k, parent_id, old_parent))


	def _observe_rpl_parent(self, payload, node_id):
		"""
		parses the respons of the parent resource (part of the dodaginfo resource). if the parent has changed, execute
		a rewiring procedure of this node to a new parent

		:param payload: the parent of the node
		:type payload: string
		:param node_id: node which broadcasted this dodaginfo
		:type node_id: :class:`node.NodeID`

		"""
		assert isinstance(payload,list)

		#if the node is the border router do nothing
		if len(payload) == 0 or node_id == self.root_id:
			return
		#create an nodeid object for the (supposed) new parent
		newparent_id = NodeID(payload[0])
		#check if its indeed a parent rewiring
		if str(newparent_id) == str(self.dodag.get_parent(node_id)):
			return

		#remove it from the lost child list if it is on there
		if node_id in self.lost_children:
			logg.debug("lost child returned to the network: " + str(node_id) + " to parent " + str(newparent_id))
			#and report it
			self.lost_children.pop(node_id,0)
		else:#otherwise just report the rewiring
			logg.debug("parent rewiring of node: " + str(node_id) + " to parent " + str(newparent_id))

		#save the old parent
		oldparent = self.dodag.get_parent(node_id)
		#update the dodag tree
		self.dodag.switch_parent(node_id,newparent_id)
		#do internal cleanup
		self.communicate(self._rewired(node_id, oldparent, newparent_id))
		#do a kickback to the api
		self.communicate(self.rewired(node_id, oldparent, newparent_id))
		#dump the new graph to file
		self._DumpGraph()

	def _rewired(self, node_id, old_parent, new_parent):
		if self.rewireframe == "":
			return []
		F = self.frames[self.rewireframe]
		q = interface.BlockQueue()
		cells = F.get_cells_similar_to(tx_node = node_id, rx_node=old_parent) + F.get_cells_similar_to({"rx_node":node_id,"tx_node":old_parent})
		for c in cells:
			q.push(Command('delete', c.owner, terms.get_resource_uri('6TOP', 'CELLLIST', ID=str(c.id))))
		q.block()
		return [q]

	#dumps a png of the current internal dodag graph with timestamp to file
	def _DumpGraph(self):
		"""
		Saves the current dodag graph to file with as filename the timestamp of the current time

		"""
		tijd = datetime.datetime.time(datetime.datetime.now())
		filename = str(tijd.hour) + ":" + str(tijd.minute) + ":" + str(tijd.second) + ".png"
		dotdata = self.dodag.draw_graph(graphname=filename)
		logg.debug("Dumped dodag graph to file: " + filename)
		packet = "[\"" + str(self.root_id) + " at " + time.strftime("%Y-%m-%d %H:%M:%S") + "\"," + json.dumps(dotdata) + "]"
		try:
			self.socket.sendall(bytearray(packet))
		except:
			pass

	def _get_rpl_dag(self, response):
		"""
		callback for the dodaginfo observe resource. This resource consists off a 2 item list with at first position
		the parent and the second item the children list

		:param response: the incomming data package
		:type response: :class:`txthings.coap.Message`

		"""
		#verify the token
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		session_id = self.cache[tk]["session"]
		#check if the response is valid
		node_id = NodeID(response.remote[0], response.remote[1])
		if self.dodag.attach_node(node_id):
			self._connect(node_id)
			self.connected(node_id)
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			cached_entry = self._decache(tk)
			self._touch_session(cached_entry['command'], session_id)
			raise exception.UnsupportedCase(tmp)

		#report to the logger
		logg.debug("Observed rpl/dag from " + str(response.remote[0]) + " >> " + parser.clean_payload(response.payload))
		try:
			#json parse the payload and decache the token
			payload = json.loads(parser.clean_payload(response.payload))
			cached_entry = self._decache(tk)
			#pass the seperate pieces of information to their functions
			if cached_entry['command'].uri.startswith(terms.get_resource_uri('RPL','DAG','PARENT')):
				self._observe_rpl_parent(payload, node_id)
			elif cached_entry['command'].uri.startswith(terms.get_resource_uri('RPL','DAG','CHILD')):
				self._observe_rpl_children(payload, node_id)
			else:
				self._observe_rpl_parent(payload[terms.resources['RPL']['DAG']['PARENT']['LABEL']], node_id)
				self._observe_rpl_children(payload[terms.resources['RPL']['DAG']['CHILD']['LABEL']], node_id)
		except ValueError as ve:
			logg.critical(ve.message+'. Command is skipped')

		# Make sure the command is removed from the session it belongs to. If the session is empty, it will also be removed
		# from the session registry. Otherwise, commands from the next block of this session will be transmitted
		self._touch_session(cached_entry['command'], session_id)

	def _post_6top_slotframe(self, response):
		"""
		Callback for slotframe resource. Triggered upon reception of a reply on the POST 6t/6/sf command. Records the slotframe
		identifier returned by the responder.

		The responder returns its local ID generated by 6top once the new frame was set with the POST 6t/6/sf command.
		As each node may return a different ID for the same slotframe, the returned ID is recorded so that future requests
		with references to that frame are possible.

		:param response: the response returned by a node after a POST 6t/6/sf request
		:type response: :class:`txthings.coap.Message`
		:raises: UnsupportedCase
		"""
		###################
		# TODO: following part same as with other callback functions... maybe make one function to handle that?
		tk = self.client.token(response.token)
		if tk not in self.cache:
			return
		session_id = self.cache[tk]["session"]
		node_id = NodeID(response.remote[0], response.remote[1])
		if response.code != coap.CONTENT:
			tmp = str(node_id) + ' returned a ' + coap.responses[response.code] + '\n\tRequest: ' + str(self.cache[tk])
			cached_entry = self._decache(tk)
			self._touch_session(cached_entry['command'], session_id)
			raise exception.UnsupportedCase(tmp)
		clean_payload = parser.clean_payload(response.payload)
		logg.debug("Node " + str(response.remote[0]) + " replied on a slotframe post with " + clean_payload + " i.e. MID:" + str(response.mid))
		try:
			payload = json.loads(clean_payload)
			###################
			posted_frames = self.cache[tk]['command'].attachment()['frames']
			posted_payload = self.cache[tk]['command'].payload
			if isinstance(posted_payload, dict) and len(payload) == 1:
				posted_payload = [posted_payload]
			i = 0
			while i < len(payload):
				fd = posted_payload[i][terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]
				frame = posted_frames[fd]
				if payload[i] == 1:
					# Make sure the local copy of the global slotframe registers the local id returned by responder node
					self.communicate(self._frame(node_id, frame, fd, posted_payload[i]))
				# Let user defined actions/commands run as soon as the frame id is registered
				self.communicate(self.framed(node_id, frame, fd if payload[i] == 1 else None, posted_payload[i]))
				i += 1
		except ValueError as ve:
			logg.critical(ve.message+'. Command is skipped')
			self.communicate(self.framed(node_id, None, None, self.cache[tk]['command'].payload))
		cached_entry = self._decache(tk)
		self._touch_session(cached_entry['command'], session_id)

	def _post_6top_link(self, response):
		"""
		Callback for cell resource. Triggered upon reception of a reply on the POST 6t/6/cl command. Records the cell
		identifier returned by the responder.

		The responder returns the local ID generated by 6top once the new cell was installed with the POST 6t/6/cl command.
		The returned ID is recorded so that future requests with references to that cell e.g. GET 6t/6/cl/5 are possible.

		:param response: the response returned by a node after a POST 6t/6/cl request
		:type response: :class:`txthings.coap.Message`
		:raises: UnsupportedCase
		"""
		###################
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
		try:
			payload = json.loads(clean_payload)
			###################
			# Extract from cache the payload of te command that triggered this response
			old_payload = self.cache[tk]['command'].payload
			attached_frame = self.cache[tk]['command'].attachment('frame')
			# If successful installation of link, insert the link into local link container
			if isinstance(payload, list):
				for i in payload:
					if isinstance(i, (int, long)):
						success = i > 0
						so = old_payload[terms.resources['6TOP']['CELLLIST']['SLOTOFFSET']['LABEL']]
						co = old_payload[terms.resources['6TOP']['CELLLIST']['CHANNELOFFSET']['LABEL']]
						lo = old_payload[terms.resources['6TOP']['CELLLIST']['LINKOPTION']['LABEL']]
						lt = old_payload[terms.resources['6TOP']['CELLLIST']['LINKTYPE']['LABEL']]
						tx = self.cache[tk]['command'].attachment('tx')
						rx = self.cache[tk]['command'].attachment('rx')
						if success:
							self.communicate(self._cell(node_id, tx, rx, so, co, attached_frame, lo, lt, old_payload))
							self.communicate(self.celled(node_id, tx, rx, so, co, attached_frame, lo, lt, old_payload))
						else:
							logg.warning("Node " + str(response.remote[0]) + " could not set the link " + str(i))
							self.communicate(self.celled(node_id, tx, rx, so, co, attached_frame, None, None, old_payload))
					else:
						logg.critical("Node " + str(response.remote[0]) + " replied on a link post with invalid payload format i.e. " + str(i) + ". Integer was expected.")
						self.communicate(self.celled(node_id, None, None, None, None, None, None, None, old_payload))
		except ValueError as ve:
			logg.critical(ve.message+'. Command is skipped')
			self.communicate(self.celled(node_id, None, None, None, None, None, None, None, old_payload))

		# Remove cached command that triggered this response
		cached_entry = self._decache(tk)
		self._touch_session(cached_entry['command'], session_id)

	def _receive_deletion(self, response):
		"""
		Callback for deletion of cell

		:param response: the response returned by a node
		:type response: :class:`txthings.coap.Message`
		:raises: UnsupportedCase
		"""

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
		cached_entry = self._decache(tk)
		self.communicate(self._delete(node_id, cache_entry['command'].uri, clean_payload))
		self.communicate(self.deleted(node_id, cache_entry['command'].uri, clean_payload))
		self._touch_session(cached_entry['command'], session_id)

	def _receive_probe(self, response):
		"""
		Callback for any other (i.e. not children, frame or cells) resource.

		Triggered upon reception of a reply on POST, DELETE commands on i.e. 6t/6/sm etc. This can be coupled with
		:func:`_get_resource` function to implement a 2-way handshake.
		It supports POST 6t/6/sm for defining a statistics metrics resource (receive its id) and then use the returned id
		to GET/OBSERVE 6t/6/sm/0 its reported values via :func:`_get_resource` function. Extensible for any other command/resource
		but payload will passed to :func:`probed` uninterpreted in JSON format as a dictionary or list.

		:param response: the response returned by a node after any request excluding GET rpl/c, POST 6t/6/sf, POST 6t/6/cl
		:type response: :class:`txthings.coap.Message`
		:raises: UnsupportedCase
		"""
		###################
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
		###################
		info = None
		if cache_entry['command'].uri == terms.uri['6TP_SM']:
			info = payload[0]
		else:
			info = payload
		cached_entry = self._decache(tk)
		self.communicate(self._probe(node_id, cache_entry['command'].uri, info))
		self.communicate(self.probed(node_id, cache_entry['command'].uri, info))
		self._touch_session(cached_entry['command'], session_id)

	def _get_resource(self, response):
		"""
		Callback for any other (i.e. not children, frame or cells) resource.

		Though similar to :func:`_receive_probe`, the semantics are different. It is meant to be triggered by responses on
		GET/OBSERVE commands on i.e. 6t/6/sf or 6t/6/sm etc whereas :func:`_receive_probe` is meant more for POST/DELETE.
		It already supports GET/OBSERVE 6t/6/sm/<id> and 6t/6/cl/<id> for getting reports on the values of statistics metrics
		and contents of cells.
		:note: Currently GET/OBSERVE 6t/6/sm is not supported. However, GET/OBSERVE 6t/6/cl is.

		:param response: the response returned by a node after any request excluding GET rpl/c, POST 6t/6/sf, POST 6t/6/cl
		:type response: :class:`txthings.coap.Message`
		:raises: UnsupportedCase
		"""
		###################
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
		logg.debug("probe on " + str(response.remote[0]) + " reported " + clean_payload + " i.e. MID:" + str(response.mid))
		uri = cache_entry['command'].uri
		try:
			payload = json.loads(clean_payload)
			self.communicate(self._report(node_id, uri, payload))
			self.communicate(self.reported(node_id, uri, payload))
		except ValueError as ve:
			logg.critical(ve.message+'. Command is skipped')
			self.communicate(self.reported(node_id, uri, None))
		cached_entry = self._decache(tk)
		self._touch_session(cached_entry['command'], session_id)

	def _push_command(self, comm, session):
		"""
		Registers the callbacks for a given URI and starts the coap client for them

		:param comm: the command itself on which the callback needs to be registered
		:type comm: :class:`interface.Command`
		:param session:
		:type session:

		"""
		# determines which function will be called regarding the used URI
		if isinstance(comm, Command):
			if not comm.callback: # TODO: what if operation/resource not supported?
				if comm.uri.startswith(terms.get_resource_uri('RPL', 'DAG')):
					if comm.op == 'get' or comm.op == 'observe':
						comm.callback = self._get_rpl_dag
				elif comm.uri.startswith(terms.get_resource_uri('6TOP', 'SLOTFRAME')):
					if comm.op == 'post':
						for f in comm.payload if isinstance(comm.payload, list) else [comm.payload]:
							to_be_transferred_id = f[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]
							slotframes = comm.attachment('frames')
							current_frame_id = slotframes[to_be_transferred_id].get_alias_id(comm.to)
							if current_frame_id is None and to_be_transferred_id is None:
								logg.warning("Posting frame to " + str(comm.to) + " FAILED >> " + comm.op + " " + comm.uri + " -- " + str(comm.payload) + " ** INCORRECT SLOTFRAME ID **")
								return
							elif current_frame_id is not None and current_frame_id != to_be_transferred_id:
								f[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']] = current_frame_id
								slotframe = slotframes[to_be_transferred_id]
								del slotframes[to_be_transferred_id]
								slotframes[current_frame_id] = slotframe
								comm.attach(frames=slotframes)
						comm.callback = self._post_6top_slotframe
					elif comm.op == 'get' or comm.op == 'observe':
						comm.callback = self._get_resource
					# elif comm.op == 'delete': TODO: support slotframe deletion
					# 	comm.callback = self._get_resource
				elif comm.uri.startswith(terms.get_resource_uri('6TOP', 'CELLLIST')):
					if comm.op == 'post':
						comm.callback = self._post_6top_link
						if not isinstance(comm.payload[terms.resources['6TOP']['CELLLIST']['SLOTFRAME']['LABEL']], (long, int)):
							logg.warning("Link " + str(comm.payload) + " to " + str(comm.to) + " was not posted. Slotframe not known to node")
							return
					elif comm.op == 'get' or comm.op == 'observe':
						slotframe = comm.attachment('frame')
						if isinstance(slotframe, Slotframe):
							queries = re.split('&|=', comm.query)
							comm.query = None
							i = 0
							j = 0
							for q in queries:
								if q == terms.resources['6TOP']['CELLLIST']['SLOTFRAME']['LABEL']:
									current_frame_id = slotframe.get_alias_id(comm.to)
									if current_frame_id is not None and current_frame_id != queries[i+1]:
										queries[i+1] = current_frame_id
								if i%2 == 0 and queries[i+1] is not None and queries[i+1] != 'None':
									if j > 0:
										comm.query += '&'
									else:
										comm.query = ''
									comm.query += str(q)
									j += 1
								elif i%2 == 1 and q is not None and q != 'None':
									comm.query += '='+str(q)
								i += 1
						comm.callback = self._get_resource
					# elif comm.op == 'delete': TODO: support celllist deletion
					# 	comm.callback = self._get_resource
				elif comm.uri == terms.uri['6TP_SM']:
					comm.callback = self._receive_probe
				elif comm.uri.startswith(terms.uri['6TP_SM']):
					comm.callback = self._get_resource
				else:
					comm.callback = self._get_resource
			self.cache[comm.id] = {'session': session, 'command': copy.copy(comm) }
			logg.info("Sending to " + str(comm.to) + " >> " + comm.op + " " + comm.uri + " -- " + str(comm.payload))
			if comm.op == 'get':
				self.client.GET(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'observe':
				self.client.OBSERVE(comm.to, comm.uri, comm.id, comm.callback)
			elif comm.op == 'post':
				self.client.POST(comm.to, comm.uri, parser.construct_payload(comm.payload), comm.id, comm.callback)
			elif comm.op == 'delete':
				self.client.DELETE(comm.to, comm.uri, comm.id, comm.callback)

	def _connect(self, child, parent=None, old_parent=None):
		"""
		is called when a new node connects, simply installes the observer for the dodaginfo resource.
		parent and old_parent are deprecated

		"""

		q = interface.BlockQueue()
		# q.push(Command('observe', child, terms.uri['RPL_OL']))
		q.push(Command('observe', child, terms.get_resource_uri('RPL', 'DAG')))
		rpl_dag_comm = Command('get', child, terms.get_resource_uri('6TOP', 'SLOTFRAME'))
		rpl_dag_comm.attach(intent='replicate')
		q.push(rpl_dag_comm)
		q.block()
		celllist_comm = Command('get', child, terms.get_resource_uri('6TOP', 'CELLLIST'))
		celllist_comm.attach(intent='replicate')
		q.push(celllist_comm)
		q.block()
		return q

	def _disconnect(self, node_id, children):
	# handles the case of a node disconnects from the network
		logg.info(str(node_id) + " was removed from the network")
		q = interface.BlockQueue()
		for (name, frame) in self.frames.items():
			deleted_cells = frame.delete_links_of(node_id)
			for cell in deleted_cells:
				if cell.owner != node_id:
					try:
						self.socket.sendall(json.dumps(["changecell",{"who": cell.owner, "channeloffs":cell.channel, "slotoffs":cell.slot, "frame":str(frame), "id":"foo", "status":0}]))
					except:
						pass
					q.push(Command('delete', cell.owner, terms.uri['6TP_CL']+'/'+str(cell.id)))
			del frame.fds[node_id]
		q.block()
		#query the new children on where they went
		for child in children:
			q.push(Command('get', child, terms.uri['RPL_DODAG']))
		q.block()
		return q

	def _frame(self, who, frame, remote_fd, old_payload):
	# handles the actions performed when a node receives his slotframes
		if frame and isinstance(frame, Slotframe):
			frame.set_alias_id(who, remote_fd)
			logg.info(str(who) + " installed new " + frame.name + " frame with id=" + str(remote_fd))
		else:
			logg.warning(str(who) + " tried to install an invalid frame: " + str(frame))
		return None

	def _register_frames(self, frames):
		# try:
		l = []
		for frame in frames:
			l.append({"id":frame.name,"cells":frame.slots})
			self.frames[frame.name] = frame
			self.blacklisted[frame.name] = []
		try:
			self.socket.sendall(json.dumps(l))
		except:
			pass

	def _cell(self, who, slotoffs, channeloffs, frame, linkoption, linktype, target, old_payload):
		# handles the actions performed when a node receives his cell/s
		# add the cell to the appropriate cell container
		frame.cell_container.append(Cell(who, slotoffs, channeloffs, frame.get_alias_id(who), linktype, linkoption, target))
		logg.info(str(who) + " installed new cell in frame " + frame.name + " at slotoffset=" + str(slotoffs) + " and channel offset=" + str(channeloffs))
		#try sending this info to the visualizer
		try:
			self.socket.sendall(json.dumps(["changecell",{"who":str(who), "slotoffs":slotoffs,"channeloffs": channeloffs,"frame": str(frame), "status" : 1}]))
		except:
			pass
		return None

	def _blacklist(self, who, slotoffs, channeloffs, frame, remote_cell_id):
		#TODO: support removal of blacklisting
		#blacklists given cell in given frame
		#TODO: append to existing list
		blacklisted = []
		F = self.frames[frame]
		cchannel = channeloffs
		cslot = slotoffs
		#forward
		while True:
			#use a wraparound for the matrix coordinate to keep moving through the matrix
			blacklisted.append([(cchannel + 16) % 16, cslot])
			cchannel += 1
			cslot += 1
			if cslot >= F.slots:
				break
		#reset indices to leftup of beginpoint
		cchannel = channeloffs - 1
		cslot = slotoffs - 1
		#and backward propagation
		while True:
			blacklisted.append([(cchannel + 16) % 16, cslot])
			cchannel -= 1
			cslot -= 1
			if cslot < 0:
				break

		#register the blacklisting
		self.blacklisted[frame] = blacklisted
		#check for every cell if its allocated and set it for rescheduling
		reschedulecells = []
		# cell = F.get_cells_similar_to({"channel":channeloffs})
		q = interface.BlockQueue()
		for blc in blacklisted:
			#this should return only one entry
			cells = F.get_cells_similar_to(channel=blc[0], slot=blc[1])
			if len(cells) == 0:
				#there has nothing been scheduled here
				continue
			#send delete commands
			for c in cells:
				q.push(Command('delete', c.owner, terms.uri['6TP_CL'] + '/' + str(c.id)))
			reschedulecells += cells
		q.block()
		#send it to the network
		self.communicate(q)
		#delete the cells from the internal frame object
		F.delete_cells(reschedulecells)
		#report it to logger
		logg.debug("Blacklisted cell with channeloffset: " + str(channeloffs) + " and slotoffset: " + str(slotoffs) + " and all asociates in frame " + F.name)

		#try sending it to the streaming server
		#only one cell has to be given as the visualizer will calculate the rest to keep network traffic down
		try:
			self.socket.sendall(json.dumps(["changecell", {"who":str(who), "slotoffs":slotoffs,"channeloffs": channeloffs,"frame": frame,"id": str(remote_cell_id), "status":2}]))
		except:
			pass

		#return all the cells that need to be rescheduled
		#build a set of (tx,rx) nodeID items (to prevent duplicates)
		s = Set()
		for c in reschedulecells:
			s.add((c.tx,c.rx))
		return list(s)

	def _probe(self, who, resource, info):
		logg.info('Probe at ' + str(who) + ' on ' + str(resource) + ' returned ' + str(info))
		return None

	def _report(self, who, resource, info):
		logg.info('Probe at ' + str(who) + ' on ' + str(resource) + ' reported ' + str(info))
		if str(resource).startswith(terms.get_resource_uri('6TOP', 'SLOTFRAME')):

			payload = copy.copy(info)
			if isinstance(payload, dict):
				payload = [payload]
			to_pop = []
			for local_frame in self.frames.itervalues():
				i = 0
				for frame in payload:
					if local_frame.get_alias_id(who) == frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]:
						logg.warning(str(who)+' holds the slotframe ID '+ str(frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]) + ' also held by ' + str(local_frame) + ' Are they identical slotframes?')
						self.framed(who, None, frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']], frame)
						to_pop.append(i)
						break
					i += 1
				for j in to_pop:
					payload.pop(to_pop[j])
			for local_frame in self.frames.itervalues():
				i = 0
				for frame in payload:
					if frame[terms.resources['6TOP']['SLOTFRAME']['SLOTS']['LABEL']] == local_frame.slots:
						if local_frame.get_alias_id(who) is None:
							self._frame(who, local_frame, frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']], info)
							payload.pop(i)
							break
						elif local_frame.get_alias_id(who) == frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]:
							payload.pop(i)
							break
					i += 1
			for remaining_frame in payload:
				frame = Slotframe(who.eui_64_ip+'#'+str(remaining_frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']]),remaining_frame[terms.resources['6TOP']['SLOTFRAME']['SLOTS']['LABEL']])
				frame.set_alias_id(who, remaining_frame[terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']])
				self.frames[frame.name] = frame
		elif str(resource) == terms.get_resource_uri('6TOP', 'CELLLIST'):
			payload = copy.copy(info)
			for link in payload:
				frame = link[terms.resources['6TOP']['CELLLIST']['SLOTFRAME']['LABEL']]
				slot = link[terms.resources['6TOP']['CELLLIST']['SLOTOFFSET']['LABEL']]
				channel = link[terms.resources['6TOP']['CELLLIST']['CHANNELOFFSET']['LABEL']]
				option = link[terms.resources['6TOP']['CELLLIST']['LINKOPTION']['LABEL']]
				type = link[terms.resources['6TOP']['CELLLIST']['LINKTYPE']['LABEL']]
				target = NodeID(link[terms.resources['6TOP']['CELLLIST']['TARGETADDRESS']['LABEL']]) if terms.resources['6TOP']['CELLLIST']['TARGETADDRESS']['LABEL'] in link else None
				retrieved_link = Cell(who, slot, channel, frame, type, option, target)
				added = False
				for f in self.frames.values():
					if f.get_alias_id(who) == frame:
						f.add_link(retrieved_link)
						added = True
				if not added:
					logg.critical('Unknown frame id='+str(frame)+'. Link '+str(retrieved_link)+' could not be stored in centralized schedule.')
		return None

	def _delete(self, who, resource, info):
		logg.info('Deletion confirmed at ' + (str(who) + " on " + str(resource) + ' : ' + str(info)))
		return None

	def communicate(self, assembly):
		"""
		Handle all the communication with the RICH network.
		"""
		if isinstance(self.start_commands, list):
			self.start_commands.append(assembly)
			return

		if isinstance(assembly, interface.BlockQueue):
			self._create_session(assembly)
		elif isinstance(assembly, list):
			for i in assembly:
				if isinstance(i, interface.BlockQueue):
					self._create_session(i)

	def connected(self, child, parent=None, old_parent=None):
		"""
		api call back for when a new node connects to the network
		This callback is fired AFTER the dodag tree has been updated

		:param child:
		:param parent:
		:param old_parent:
		:return:
		"""
		pass

	def disconnected(self, node_id):
		"""
		api callback for when a node disconnects
		This callback is fired AFTER the dodag tree has been updated

		:param node_id:
		:return:
		"""
		pass

	def rewired(self, node_id, old_parent, new_parent):
		"""
		api callback for when a node has been rewired in the dodag tree by rpl. This callback is fired AFTER the dodag
		tree has been updated, returns a list of blockqueue for commands to the network

		:param node_id:
		:param old_parent:
		:param new_parent:
		:return:
		"""
		pass

	def framed(self, who, local_name, remote_alias, old_payload):
		pass

	def celled(self, who, tx, rx, slotoffs, channeloffs, frame, linkoption, linktype, old_payload):
		pass

	def deleted(self, who, resource, info):
		pass

	def probed(self, node, resource, value):
		pass

	def reported(self, node, resource, value):
		pass


class SchedulerInterface(Reflector):

	def start(self):
		q = interface.BlockQueue()
		q.push(Command('get', self.root_id, terms.get_resource_uri('RPL', 'DAG')))
		q.block()
		self.communicate(q)

		super(SchedulerInterface, self)._start()


	def get_slotframes(self, node):  # TODO: observe (makes sense when distributed scheduling in place)
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		q.push(Command('get', node, terms.get_resource_uri('6TOP','SLOTFRAME')))
		q.block()
		return q

	def get_slotframe_by_id(self, node, slotframe):
		assert isinstance(node, NodeID)
		if isinstance(slotframe, Slotframe):
			alias = slotframe.get_alias_id(node)
			if alias:
				q = interface.BlockQueue()
				q.push(Command('get', node, terms.get_resource_uri('6TOP','SLOTFRAME', ID=alias)))
				q.block()
				return q
		elif isinstance(slotframe, (int, long)):
			q = interface.BlockQueue()
			q.push(Command('get', node, terms.get_resource_uri('6TOP','SLOTFRAME', ID=slotframe)))
			q.block()
			return q
		logg.warning('Slotframe '+str(slotframe)+' is not a valid slotframe ID. Operation is skipped.')
		return None

	def get_slotframe_by_size(self, node, size):
		assert isinstance(node, NodeID)
		assert isinstance(size, (int, long))
		q = interface.BlockQueue()
		q.push(Command('get', node, terms.get_resource_uri('6TOP','SLOTFRAME', SLOTS=size)))
		q.block()
		return q

	def post_slotframes(self, node, slotframes):
		assert isinstance(node, NodeID)
		assert isinstance(slotframes, Slotframe) or isinstance(slotframes, list)
		if isinstance(slotframes, Slotframe):
			slotframes = [slotframes]
		q = interface.BlockQueue()
		payload = []
		info = {}
		frame_id = 255
		for item in slotframes:
			while frame_id >= 0:
				free = True
				for name, frame in self.frames.items():
					tmp = frame.get_alias_id(node)
					if tmp == frame_id:
						free = False
						break
				if free:
					break
				frame_id -= 1
			info[frame_id] = item
			payload.append({terms.resources['6TOP']['SLOTFRAME']['ID']['LABEL']: frame_id,
							terms.resources['6TOP']['SLOTFRAME']['SLOTS']['LABEL']: item.slots})
		if len(payload) == 1:
			payload = payload[0]
		comm = Command('post', node, terms.get_resource_uri('6TOP','SLOTFRAME'), payload)
		comm.attach(frames=info)
		q.push(comm)
		q.block()
		return q

	def get_links(self, node):
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST')))
		q.block()
		return q

	def get_link_by_coords(self, node, slotframe, slot, channel):
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		if isinstance(slotframe, (int, long)):
			q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST', SLOTFRAME=slotframe, SLOTOFFSET=slot, CHANNELOFFSET=channel)))
			q.block()
			return q
		elif isinstance(slotframe, Slotframe):
			alias = slotframe.get_alias_id(node)
			if alias:
				q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST', SLOTFRAME=alias, SLOTOFFSET=slot, CHANNELOFFSET=channel)))
				q.block()
				return q
		return None

	def get_link_by_id(self, node, link):
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		if link is None:
			q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST')))
		elif isinstance(link, (int, long)):
			q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST', ID=str(link))))
		elif isinstance(link, Cell) and link.id:
			q.push(Command('get', node, terms.terms.get_resource_uri('6TOP', 'CELLLIST', ID=str(link.id))))
		else:
			return None
		q.block()
		return q

	def get_link_by_slotframe(self, node, slotframe):
		assert isinstance(node, NodeID)
		q = interface.BlockQueue()
		if isinstance(slotframe, (int, long)):
			q.push(Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST', SLOTFRAME=slotframe)))
			q.block()
			return q
		elif isinstance(slotframe, Slotframe):
			alias = slotframe.get_alias_id(node)
			comm = Command('get', node, terms.get_resource_uri('6TOP', 'CELLLIST', SLOTFRAME=alias))
			comm.attach(frame=slotframe)
			q.push(comm)
			q.block()
			return q
		return None

	def post_link(self, slot, channel, slotframe, source, destination, target=None):
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
			comm = Command('post', c.owner, terms.get_resource_uri('6TOP','CELLLIST'), {
				terms.resources['6TOP']['CELLLIST']['SLOTOFFSET']['LABEL']:c.slot,
				terms.resources['6TOP']['CELLLIST']['CHANNELOFFSET']['LABEL']:c.channel,
				terms.resources['6TOP']['CELLLIST']['SLOTFRAME']['LABEL']: slotframe.get_alias_id(c.owner),
				terms.resources['6TOP']['CELLLIST']['LINKOPTION']['LABEL']:c.option,
				terms.resources['6TOP']['CELLLIST']['LINKTYPE']['LABEL']:c.type
			})
			comm.attach(frame = slotframe)
			comm.attach(tx = c.tx)
			comm.attach(rx = c.rx)
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
			q.push(Command('get' if not observe else 'observe', node, terms.uri['6TP_SM']+'/'+str(statistics)))
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
				if item.rx == tx or (item.rx is None and (item.tx == self.dodag.get_parent(tx) or item.tx in self.dodag.get_children(tx))) or \
					item.tx == tx:
						return True
				elif (item.rx is not None and item.rx == rx) or \
					(item.rx is None and rx is not None and item.tx in self.dodag.get_neighbors(rx)) or \
					(item.rx is not None and rx is None and tx in self.dodag.get_neighbors(item.rx)) or \
					(rx is None and item.rx is None and not set(self.dodag.get_neighbors(tx)).isdisjoint(set(self.dodag.get_neighbors(item.tx)))) or \
					(rx is None and item.tx == self.dodag.get_parent(tx)) or item.tx == rx:
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

	def blacklist(self, channel, slot, slotframe):
		return [channel, slot] in self.blacklisted[str(slotframe)]

	def schedule(self, tx, rx, slotframe):
		raise NotImplementedError()