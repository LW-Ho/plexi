__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.1"
__copyright__ = "Copyright 2015, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"


#!/bin/python

__author__ = "George Exarchakos"
__email__ = "g.exarchakos@tue.nl"
__version__ = "0.0.1"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

import getopt
import sys

class UserInput:
	def __init__(self, netname, lbr, port, prefix, visualizer):
		self.network_name = netname
		self.lbr = lbr
		self.port = port
		self.prefix = prefix
		self.visualizer = visualizer


def usage():
	print('Command:\trischer.py [-h][-b[-p][-v]]')
	print('Options:')
	print('\t-h,\t--help\t\t\tthis usage message')
	print('\t-b,\t--LBR=\t\t\tIPv6 address of Low-Power and Lossy Network Border Router e.g. 215:8d00:52:68c7 or aaaa::215:8d00:52:68c7 (port:5684 assumed)')
	print('\t-p,\t--prefix=\t\t4-character address prefix e.g. aaaa')
	print('\t-v,\t--visualizer=\tip address of FrankFancyGraphStreamer server')

def get_user_input(arg_str):
	lbr = None
	visualizer = False
	prefix = None

	try:
		if arg_str:
			opts, args = getopt.getopt(arg_str, "hb:v:p:", ["help", "LBR=", "visualizer=", "prefix="])
		else:
			opts, args = getopt.getopt(sys.argv[1:], "hb:v:p:", ["help", "LBR=", "visualizer=", "prefix="])
	except getopt.GetoptError as err:
		print(str(err))
		usage()
		return 2

	for o, a in opts:
		if o in ("-b", "--LBR"):
			lbr = a
			parts = lbr.split(':')
			if len(parts)==6:
				if prefix is not None and parts[0] != a:
					print("Cannot use -p option when the LBR address has a prefix already")
					usage()
					return 2
				prefix = parts[0]
		elif o in ("-v", "--visualizer"):
			visualizer = a
		elif o in ("-p", "--prefix"):
			if prefix is not None and prefix != a:
				print("Cannot use -p option when the LBR address has a prefix already")
				usage()
				return 2
			prefix = a
		elif o in ("-h", "--help"):
			usage()
			return
		else:
			usage()
			return 2

	if lbr is None:
		print("Border router IPv6 must be specified")
		usage()
		return 2

	if prefix is None:
		print("LBR address is missing a prefix. Specify the address as e.g. aaaa::215:8d00:52:68c7 or use the -p option")
		usage()
		return 2

	return UserInput("RICHNET", lbr, 5684, prefix, visualizer if visualizer else None)