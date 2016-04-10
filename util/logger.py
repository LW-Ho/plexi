__author__ = "George Exarchakos"
__version__ = "0.0.1"
__email__ = "g.exarchakos@tue.nl"
__maintainer__ = "George Exarchakos"
__status__ = "Pre-Alpha"
__credits__ = ["Thomas Watteyne"]
# __copyright__ = "Copyright 2007, The Cogent Project"
# __license__ = "GPL"

import logging
import logging.handlers

class NullHandler(logging.Handler):
	def emit(self, record):
		pass
nullLogger = NullHandler()

#fileLogger = logging.handlers.RotatingFileHandler(filename='test.log', mode='w', backupCount=5, )
#fileLogger.setFormatter(logging.Formatter('%(asctime)s [%(name)s:%(levelname)s] %(message)s'))

fileLogger = logging.handlers.RotatingFileHandler("logs/RiSCHER.log", maxBytes=1e6, backupCount=25)
fileLogger.setFormatter(logging.Formatter(fmt='%(asctime)s\t%(levelname)s: %(message)s', datefmt='(%d-%m)%H:%M:%S'))

consoleLogger = logging.StreamHandler()
consoleLogger.setFormatter(logging.Formatter(fmt='%(asctime)s.%(msecs)03d\t%(levelname)s: %(message)s', datefmt='%H:%M:%S'))
consoleLogger.setLevel(logging.DEBUG)

for loggerName in ['RiSCHER']:
	temp = logging.getLogger(loggerName)
	temp.setLevel(logging.DEBUG)
	# temp.addHandler(fileLogger)
	temp.addHandler(consoleLogger)
	temp.addHandler(fileLogger)
	temp.addHandler(nullLogger)