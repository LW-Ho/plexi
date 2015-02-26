__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.1"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

from collections import deque

class MilestoneQueue:
	def __init__(self):
		self.items = deque([])
		self.last_milestone = set()

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
		if id in self.last_milestone:
			return False
		self.items.append(item)
		self.last_milestone.add(id)
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
		if len(self.last_milestone) > 0:
			self.items.append(self.last_milestone)
			self.last_milestone = set()
			return True
		return False