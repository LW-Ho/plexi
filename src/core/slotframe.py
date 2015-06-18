__author__ = "Dimitris Sarakiotis, Ilker Oztelcan, George Exarchakos"
__email__ = "d.sarakiotis@tue.nl, i.oztelcan@tue.nl, g.exarchakos@tue.nl"
__version__ = "0.0.11"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

class Slotframe(object):
	def __init__(self, name, slots):
		self.cell_container = []	# Cell container of this slotframe
		self.slots = slots			# Size of this slotframe in number of slots
		self.name = name			# Scheduler-assigned reference name of this slotframe
		self.fds = {}   			# Node-assigned ids of this slotframe in (key : value) format --> (node : sf_id)
		c_minimal = Cell(None, 0, 0, None, None, None, 0, 7)
		self.cell_container.append(c_minimal)

	@property
	def Slots(self):
		return self.slots

	def get_alias_id(self, node):
		if node in self.fds.keys():
			return self.fds[node]
		return None

	def set_alias_id(self, node, id):
		self.fds[node] = id

	def get_cells_similar_to(self, **kwargs):
		matching_cells = []
		for i in self.cell_container:
			if 'owner' in kwargs.keys() and kwargs['owner'] != i.owner:
				continue
			if 'slot' in kwargs.keys() and kwargs['slot'] != i.slot:
				continue
			if 'channel' in kwargs.keys() and kwargs['channel'] != i.channel:
				continue
			if 'link_option' in kwargs.keys() and kwargs['link_option'] != i.option:
				continue
			if 'cell_id' in kwargs.keys() and kwargs['cell_id'] != i.id:
				continue
			if 'frame_id' in kwargs.keys() and kwargs['frame_id'] != i.slotframe:
				continue
			if 'tx_node' in kwargs.keys() and kwargs['tx_node'] != i.tx:
				continue
			if 'rx_node' in kwargs.keys() and kwargs['rx_node'] != i.rx:
				continue
			matching_cells.append(i)
		return matching_cells

	def get_cells_of(self, node_id):
		all_cells = []
		for item in self.cell_container:
			if item.owner == node_id:
				all_cells.append(item)
		return all_cells

	def delete_links_of(self, node_id):
		deleted_cell_container = []
		for item in self.cell_container:
			# if item.owner == node_id or item.tx_node == node_id or item.rx_node == node_id:
			if item.owner == node_id:
				deleted_cell_container.append(item)
		self.delete_cells(deleted_cell_container)
		# for dltd in deleted_cell_container:
		# 	self.cell_container.remove(dltd)
		return deleted_cell_container

	def delete_cells(self, cells):
		for cell in cells:
			self.cell_container.remove(cell)

	def set_remote_cell_id(self,who,channel,slot,remote_id):
		for c in self.cell_container:
			if c.owner == who and c.channel == channel and c.slot == slot:
				c.id = remote_id
				return

	def __str__(self):
		return self.name

class Cell(object):
	def __init__(self, node, so, co, tx, rx, fd, lt, lo):
		self._cell_id = None		# Cel ID as set by the owner
		self._owner = node		# The node to which this cell belongs to
		self._slotframe_id = fd		# The local frame id (that of the owner), the cell belongs to
		self._channel = co		# Channel offset
		self._slot = so			# Slot offset
		self._tx_node = tx
		self._rx_node = rx
		self._link_type = lt
		self._link_option = lo 		# For unicast Tx is 1, for unicast Rx is 2, for broadcast Tx is 9, for broadcast Rx is 10
		#self.pending = False # TODO: is it needed?

	@property
	def id(self):
		return self._cell_id

	@id.setter
	def id(self, cd):
		self._cell_id = cd

	@property
	def owner(self):
		return self._owner

	@owner.setter
	def owner(self, node):
		self._owner = node

	@property
	def slotframe(self):
		return self._slotframe_id

	@slotframe.setter
	def slotframe(self, frame):
		self._slotframe_id = frame

	@property
	def channel(self):
		return self._channel

	@channel.setter
	def channel(self, channel_offset):
		self._channel = channel_offset

	@property
	def slot(self):
		return self._slot

	@slot.setter
	def slot(self, slot_offset):
		self._slot = slot_offset

	@property
	def tx(self):
		return self._tx_node

	@tx.setter
	def tx(self, tx_node):
		self._tx_node = tx_node

	@property
	def rx(self):
		return self._rx_node

	@rx.setter
	def rx(self, rx_node):
		self._rx_node = rx_node

	@property
	def type(self):
		return self._link_type

	@type.setter
	def type(self, lt):
		self._link_type = lt

	@property
	def option(self):
		return self._link_option

	@option.setter
	def option(self, lo):
		self.link_option = lo

	def __str__(self):
		ownership = self.owner+'/'+self.slotframe+'/'+self.id
		coordinates = '['+self.slot+','+self.channel+']'
		link = self.tx+'->'+(self.rx if self.rx else 'ALL')
		properties = '{'+self.type+','+self.option+'}'
		return ownership+':'+coordinates+':'+link+':'+properties
