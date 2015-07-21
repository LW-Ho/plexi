__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.4"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"


class FormatError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate format of input value: '+self.value

	def __str__(self):
		return self.message

class RequestError(Exception):
	def __init__(self, value):
		self.value = value
		self.message = 'Inappropriate request received: '+str(self.value)

	def __str__(self):
		return self.message

class UnsupportedCase(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return str(self.value)
