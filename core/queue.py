__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.1"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from collections import deque

class Command(object):
	token = 0
	def __init__(self, op, to, uri, payload=None, callback=None):
		self.id = Command.token
		Command.token += 1
		self.op = op
		self.to = to
		self.uri = uri
		self.content = payload
		self.callback = callback

	def __str__(self):
		return str(self.id) + ': ' + self.op + ' ' + str(self.to) + ' ' + str(self.uri) + ' ' + str(self.content) + ' ' + str(self.callback)

	@property
	def payload(self):
		return self.content

	@payload.setter
	def payload(self, load):
		if load and "frame" in load and isinstance(load["frame"], str):
			raise Exception("got you")
		self.content = load


class RendezvousQueue:
	def __init__(self):
		self.items = deque([])
		self.last_point = set()

	def pop(self):
		try:
			if not isinstance(self.items[0], set):
				return self.items.popleft()
			elif isinstance(self.items[0], set) and len(self.items[0]) == 0:
				self.items.popleft()
				return self.pop()
			else:
				return None
		except IndexError:
			return None

	def push(self, id, item):
		if id in self.last_point:
			return False
		self.items.append(item)
		self.last_point.add(id)
		return True

	def achieved(self, id):
		for i in self.items:
			if isinstance(i, set):
				if id in i:
					i.remove(id)
					return True
				break
		return False

	def bank(self):
		if len(self.last_point) > 0:
			self.items.append(self.last_point)
			self.last_point = set()
			return True
		return False

	def __len__(self):
		c_items = 0
		for i in self.items:
			if not isinstance(i, set):
				c_items += 1
		return c_items
	
	def finished(self):
		for i in self.items:
			if not isinstance(i, set) or (isinstance(i, set) and len(i)>0):
				return False
		return True

	def ready(self):
		return len(self.last_point) == 0

	def unprocessed(self):
		attendees = 0
		for i in self.items:
			if not isinstance(self.items[0], set):
				attendees += 1
			elif len(i) > attendees:
				return False
			else:
				attendees = 0
		return True

	def append(self, other_queue):
		if isinstance(other_queue, RendezvousQueue) and other_queue.ready() and other_queue.unprocessed():
			self.items.extend(other_queue.items)
		else:
			raise Exception('Impossible to append. Either not RendezvousQueue, or not ready or already processed')

	def __str__(self):
		tmp = ''
		_counter = 0
		for i in self.items:
			if isinstance(i,set):
				tmp += 'W -> [ '
				for j in i:
					tmp += str(j)+' '
				tmp += ']\n'
			else:
				tmp += str(_counter)+' -> '+str(i)+'\n'
				_counter += 1
		if len(self.last_point)>0:
			tmp += '( '
			for j in self.last_point:
				tmp += str(j)+' '
			tmp += ')\n'
		return tmp