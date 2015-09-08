__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.1"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from collections import deque
import copy

class Command(object):
	token = 0
	def __init__(self, op, to, uri, payload=None, callback=None):
		self.id = Command.token
		Command.token += 1
		self.op = op
		self.to = to
		tmp = uri.split('?')
		self.path = tmp[0]
		self.query = None
		if len(tmp) == 2:
			self.query = tmp[1]
		self.content = payload
		self.xtra = None
		self.callback = callback

	def __eq__(self, other):
		return self.id == other.id

	def __copy__(self):
		comm = Command(self.op, self.to, self.uri, copy.copy(self.payload), self.callback)
		comm.id = self.id
		tmp = self.attachment()
		if isinstance(tmp, dict):
			comm.attach(**tmp)
		return comm

	def __str__(self):
		return str(self.id) + ': ' + self.op + ' ' + str(self.to) + ' ' + str(self.uri) + ' ' + str(self.content) + ' ' + str(self.xtra) + ' ' + str(self.callback)

	@property
	def payload(self):
		return self.content

	@payload.setter
	def payload(self, load):
		if load and "frame" in load and isinstance(load["frame"], str):
			raise Exception("got you")
		self.content = load

	@property
	def uri(self):
		return self.path+'?'+self.query if self.query else self.path

	def attachment(self):
		return self.xtra

	def attach(self, **kwargs):
		if not self.xtra:
			self.xtra = {}
		for k,v in kwargs.iteritems():
			self.xtra[k] = v

	def __eq__(self, other):
		return self.id == other.id


class BlockQueue(object):
	def __init__(self):
		self.items = deque([])
		self.last_point = set()
		self._pointer = -1
		self._size = 0

	def __iter__(self):
		return self

	def next(self):
		if len(self) == 0:
			raise StopIteration
		self._pointer += 1
		if self._pointer >= self.__len__():
			self._pointer = -1
			raise StopIteration
		return self.__getitem__(self._pointer)

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
		if key < 0:
			key = self._size - key
		if 0 <= key <= self._size:
			self.items[key] = value
		else:
			raise IndexError('list assignment index out of range')

#	def __delitem__(self, key):
#		pass

#	def __contains__(self, item):
#		pass

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
		if isinstance(item, BlockQueue) and self.ready() and item.ready() and item.unprocessed():
			self.items.extend(list(item.items))
			self._size += len(item)
		elif isinstance(item, BlockQueue) and self.ready() and not item.ready() and item.unprocessed():
			self.items.extend(list(item.items))
			self._size += len(item)
			self.last_point = item.last_point
		elif isinstance(item, BlockQueue) and not self.ready() and not item.ready() and item.unprocessed() and len(item.items) == len(item):
			self.items.extend(list(item.items))
			self._size += len(item)
			self.last_point.union(item.last_point)
		elif isinstance(item, BlockQueue):
			raise Exception('Impossible to append')
		elif isinstance(item, list):
			for i in item:
				self.push(i)
		elif item in self.last_point:
			return False
		else:
			self.items.append(item)
			self._size += 1
			self.last_point.add(item)

		return True

	def unblock(self, item):
		for i in self.items:
			if isinstance(i, set):
				for j in list(i):
					if item == j:
						i.remove(j)
						return True
				break
		return False

	def block(self):
		if len(self.last_point) > 0:
			self.items.append(self.last_point)
			self.last_point = set()
			return True
		return False

	def __len__(self):
		return self._size

	def finished(self):
		return self.__len__() == 0

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

	def __str__(self):
		tmp = ''
		_counter = 0
		_idx = 0
		for i in self.items:
			if isinstance(i, set):
				assembly = []
				for j in reversed(range(_idx)):
					if isinstance(self.items[j], set):
						break
					assembly.append(j-_idx+_counter)
				tmp += str(sorted(assembly))+'\n'
			else:
				tmp += str(_counter)+' -> '+str(i)+'\n'
				_counter += 1
			_idx += 1
		if len(self.last_point) > 0:
			assembly = []
			for j in reversed(range(_idx)):
				if isinstance(self.items[j], set):
					break
				assembly.append(j-_idx+_counter)
			tmp += str(sorted(assembly))+'++\n'
		return tmp