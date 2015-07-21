#!/bin/python
import getopt
import sys

from schedule.maestro import Scheduler
from endpoint.client import LazyCommunicator
from resource.rpl import NodeID

sch = None

def usage():
	print('Command:\tping.py [-o[-p[-P]]]')
	print('Options:')
	print('\tNone,\tscheduler in operation')
	print('\t-h,\t--help=\tthis usage message')
	print('\t-a,\t--address=\tdestination node address in IP:PORT format')
	print('\t-o,\t--operation=\tGET|POST|DELETE|OBSERVE')
	print('\t-p,\t--path=\t\t\tPath of the request')
	print('\t-P,\t--payload=\t\tPayload of the request')


def client_callback(response, kwargs):
	print("Callback")


def client_callback_observe(response, kwargs):
	print("Callback_observe")
	check = True
	while check:
		chosen = input("Stop observing? [y/N]: ")
		if chosen != "" and not (chosen == "n" or chosen == "N" or chosen == "y" or chosen == "Y"):
			print("Unrecognized choose.")
			continue
		elif chosen == "y" or chosen == "Y":
			while True:
				rst = input("Send RST message? [Y/n]: ")
				if rst != "" and not (rst == "n" or rst == "N" or rst == "y" or rst == "Y"):
					print("Unrecognized choose.")
					continue
				elif rst == "" or rst == "y" or rst == "Y":
					sch.client.protocol.cancel_observing(response, True)
				else:
					sch.client.protocol.cancel_observing(response, False)
				check = False
				break
		else:
			break


def main(arg_str):
	node = None
	op = None
	path = None
	payload = None
	try:
		if arg_str:
			opts, args = getopt.getopt(arg_str, "ha:o:p:P:", ["help", "address=", "operation=", "path=", "payload="])
		else:
			opts, args = getopt.getopt(sys.argv[1:], "ha:o:p:P:", ["help", "address=", "operation=", "path=", "payload="])
	except getopt.GetoptError as err:
		# print help information and exit:
		print(str(err))  # will print something like "option -a not recognized"
		usage()
		return 2

	if not opts:
		sch = Scheduler('RICHNET', 'aaaa::215:8d00:52:6986', 5684)
		sch.start()
		return 0
	else:
		client = LazyCommunicator(5)

	for o, a in opts:
		if o in ("-o", "--operation"):
			op = a
		elif o in ("-p", "--path"):
			path = a
		elif o in ("-P", "--payload"):
			payload = a
		elif o in ('-a', '--address'):
			try:
				ip, port = a.split(':')
			except ValueError:
				ip = a[:-5]
				port = a[-4:]
			node = NodeID(ip, int(port))
		elif o in ("-h", "--help"):
			usage()
			return
		else:
			usage()
			return 2

	if op is None or node is None or path is None:
		print("Operation, destination node and path must be specified")
		usage()
		return 2

	if op == "GET":
		client.GET(node, path, 1, client_callback)
	elif op == "OBSERVE":
		client.OBSERVE(node, path, 1, client_callback_observe)
	elif op == "DELETE":
		client.DELETE(node, path, 1, client_callback)
	elif op == "POST":
		if payload is None:
			print("Payload cannot be empty for a POST request")
			usage()
			return 2
		client.POST(node, path, payload, 1, client_callback)
	else:
		print("Operation not recognized")
		usage()
		return 2
	return 0

if __name__ == '__main__':
	x = main(None)
	sys.exit(x)