__author__ = "George Exarchakos, Ilker Oztelcan, Dimitris Sarakiotis"
__version__ = "0.0.4"
__email__ = "g.exarchakos@tue.nl, i.oztelcan@tue.nl, d.sarakiotis@tue.nl"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"

# uri = {
# 	'RPL'		: "rpl",
# 	'RPL_NL'	: "rpl/nd",
# 	# 'RPL_OL'	: "rpl/c",
# 	'6TP'		: "6t",
# 	'6TP_6'		: "6t/6",
# 	'6TP_SF'	: "6t/6/sf",
# 	'6TP_CL'	: "6t/6/cl",
# 	#'6TP_SV'	: "6t/6/ml",
# 	'6TP_SM'	: "6t/6/sm",
# 	'RPL_DODAG'	: "rpl/dodag"
# }
#
# keys = {
# 	'SM_ID': "md",
# 	'SF_ID': "fd",
# 	'CL_ID': "cd",
# 	'S_OFF': "so",
# 	'C_OFF': "co",
# 	'LN_OP': "lo",
# 	'LN_TP': "lt",
# 	'TNA'  : "na",
# 	'MTRC' : "mt",
# 	'WNDW' : "wi",
# 	'RSSI' : "RSSI",
# 	'PDR'  : "pdr",
# 	'PRR'  : "PRR",
# 	'LQI'  : "LQI",
# 	'SLT'  : 'SLOT',
# 	'ETX'  : 'ETX'
# }
#
# cells = {
# 	'broadcast',
# 	'unicast'
# }

resources = {
	'RPL': {
		'LABEL': 'rpl',
		'DAG': {
			'LABEL': 'dag',
			'PARENT': {'LABEL': 'parent'},
			'CHILD': {'LABEL': 'child'}
		}
	},
	'6TOP': {
		'LABEL': '6top',
		'SLOTFRAME': {
			'LABEL': 'slotFrame',
			'ID': {'LABEL':'frame'},
			'SLOTS': { 'LABEL':'slots'}
		},
		'CELLLIST': {
			'LABEL': 'cellList',
			'ID': {'LABEL':'link'},
			'SLOTFRAME': {'LABEL': 'frame'},
			'CHANNELOFFSET': {'LABEL': 'channel'},
			'SLOTOFFSET': {'LABEL': 'slot'},
			'LINKOPTION': {'LABEL': 'option'},
			'LINKTYPE': {'LABEL': 'type'},
			'TARGETADDRESS': {'LABEL': 'tna'},
			'STATISTICS': {'LABEL': 'stats'}
		},
		'NEIGHBORLIST': {
			'LABEL': 'nbrList',
			'ASN':{ 'LABEL': 'asn'}
		},
		'STATISTICS': {
			'LABEL': 'stats',
			'ID':{ 'LABEL': 'id'},
			'METRIC':{ 'LABEL': 'metric'},
			'ENABLE':{ 'LABEL': 'enable'},
			'WINDOW':{ 'LABEL': 'window'},
			'VALUE':{ 'LABEL': 'value'},
			'RSSI':{ 'LABEL': 'rssi'},
			'LQI':{ 'LABEL': 'lqi'},
			'ETX':{ 'LABEL': 'etx'},
			'PDR':{ 'LABEL': 'pdr'}
		},
		'QUEUELIST': {
			'LABEL': 'qList',
			'ID':{ 'LABEL': 'id'},
			'TXLEN':{ 'LABEL': 'txlen'}
		}
	}
}

def get_resource_uri(*path_segments,**queries):
	uri = ''
	parent = None
	object = resources
	first_item = 1
	for rsrc in path_segments:
		if rsrc in object:
			if not first_item:
				uri += '/'
			first_item = 0
			uri += object[rsrc]['LABEL']
			parent = object
			object = object[rsrc]
		else:
			return None
	first_item = 1
	for k,v in queries.iteritems():
		if first_item == 1:
			uri += '?'
		else:
			uri += '&'
		first_item = 0
		if k in object:
			uri += object[k]['LABEL']+"="+str(v)
		elif k in parent:
			uri += parent[k]['LABEL']+"="+str(v)
		else:
			return None
	return uri

errors = {
	'GET': ['BAD_JSON', ]
}