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

	def __eq__(self, other):
		return self.id == other.id


class RendezvousQueue:
	def __init__(self):
		self.items = deque([])
		self.last_point = set()
		self.pointer = -1
		self. _size = 0

	def __iter__(self):
		return self

	def next(self):
		if len(self) == 0:
			raise StopIteration
		self.pointer += 1
		if self.pointer >= self.__len__():
			raise StopIteration
		return self.__getitem__(self.pointer)

	def __getitem__(self, item):
		if not isinstance(item, (int, long)):
			raise KeyError
		if item < 0:
			item = self.__len__()+item
		if item < 0 or len(self) == 0 or item >= 0 and item >= len(self):
			raise IndexError
		counter = 0
		index = 0
		for i in self.items:
			if counter == item and not isinstance(i, set):
				return self.items[index]
			if not isinstance(i, set):
				counter += 1
			index += 1

	def __setitem__(self, key, value):
		pass

	def __delitem__(self, key):
		pass

	def __contains__(self, item):
		pass

	def pop(self):
		try:
			if not isinstance(self.items[0], set):
				if self.items[0] in self.last_point:
					self.last_point.remove(self.items[0])
				self._size -= 1
				return self.items.popleft()
			elif isinstance(self.items[0], set) and len(self.items[0]) == 0:
				self.items.popleft()
				return self.pop()
			else:
				return None
		except IndexError:
			return None

	def push(self, item):
		if item in self.last_point:
			return False
		self.items.append(item)
		self._size += 1
		self.last_point.add(item)
		return True

	def achieved(self, item):
		for i in self.items:
			if isinstance(i, set):
				if item in i:
					i.remove(item)
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
		return self._size

	def finished(self):
		for i in self.items:
			if not isinstance(i, set) or (isinstance(i, set) and len(i) > 0):
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