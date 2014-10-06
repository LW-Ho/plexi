class NeighborList(object):
	def __init__(self):
		self.tag = 'NL'
		self.neighbors = {}

	def add(self, ta, rssi, lqi, asn):
		self.neighbors[ta] = {'RSSI': rssi, 'LQI': lqi, 'ASN': asn}

	def get(self, ta, q):
		try:
			if ta and q:
				return self.neihbors[ta][q]
			elif q and not ta:
				tmp = []
				for n in self.neighbors:
					tmp.append(n[q])
				return tmp
			elif ta and not q:
				return self.neighbors[ta]
			else:
				return None
		except:
			return None