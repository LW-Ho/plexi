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
		self.name = name			# SchedulerInterface-assigned reference name of this slotframe
		self.fds = {}   			# Node-assigned ids of this slotframe in (key : value) format --> (node : sf_id)

	# @property
	# def slots(self):
	# 	return self.slots

	def __len__(self):
		return self.slots

	def get_alias_id(self, node):
		if node in self.fds.keys():
			return self.fds[node]
		return None

	def set_alias_id(self, node, id):
		self.fds[node] = id

	def get_link_by_coords(self, slot, channel, owner):
		links = []
		for i in self.cell_container:
			if (i.slot == slot if slot else True) and (i.channel == channel if channel else True) and (i.owner == owner if owner else True):
				links.append(i)
		return links

	def add_link(self, link):
		if self.get_link_by_coords(link.slot, None, link.owner):
			return False
		same_cell_links = self.get_link_by_coords(link.slot, link.channel, None)
		if not same_cell_links:
			self.cell_container.append(link)
			return True
		else:
			for l in same_cell_links:
				if link.option & 1 and l.option & 1 and (not link.option & 3 or not l.option & 3):
					return False
		return True



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
			if 'link_type' in kwargs.keys() and kwargs['link_type'] != i.type:
				continue
			if 'slotframe' in kwargs.keys() and kwargs['slotframe'] != i.slotframe:
				continue
			if 'tna' in kwargs.keys() and kwargs['tna'] != i.tna:
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
			if item.owner == node_id or item.tna == node_id:
				deleted_cell_container.append(item)
		self.delete_cells(deleted_cell_container)
		# for dltd in deleted_cell_container:
		# 	self.cell_container.remove(dltd)
		return deleted_cell_container

	def delete_cells(self, cells):
		for cell in cells:
			self.cell_container.remove(cell)

	# def set_remote_cell_id(self,who,channel,slot,remote_id):
	# 	for c in self.cell_container:
	# 		if c.owner == who and c.channel == channel and c.slot == slot:
	# 			c.id = remote_id
	# 			return

	def __str__(self):
		return self.name

class Cell(object):
	def __init__(self, node, so, co, fd, lt, lo, tna):
		self._owner = node		# The node to which this cell belongs to
		self._slotframe_id = fd		# The local frame id (that of the owner), the cell belongs to
		self._channel = co		# Channel offset
		self._slot = so			# Slot offset
		self._link_type = lt
		self._link_option = lo 		# For unicast Tx is 1, for unicast Rx is 2, for broadcast Tx is 9, for broadcast Rx is 10
		self._target = tna

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
	def tna(self):
		return self._target

	@tna.setter
	def tna(self, node):
		self._target = node

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
		ownership = str(self.owner)+'/'+str(self.slotframe)
		coordinates = '['+str(self.slot)+','+str(self.channel)+']'
		properties = '{'+str(self.type)+','+str(self.option)+'}'
		return ownership+':'+coordinates+':'+':'+properties
