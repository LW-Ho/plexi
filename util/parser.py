__author__ = "George Exarchakos"
__version__ = "0.0.2"
__email__ = "g.exarchakos@tue.nl"
__copyright__ = "Copyright 2014, The RICH Project"
#__credits__ = ["XYZ"]
#__maintainer__ = "XYZ"
#__license__ = "GPL"
#__status__ = "Production"


from exception import FormatError
import string

def query_to_dictionary(query):
	if isinstance(query, basestring):
		d = {}
		query_list = query.split('&')
		for i in query_list:
			tmp = i.split('=')
			if len(tmp) < 2:
				raise FormatError(query)
			d[tmp[0]] = tmp[1]
		return d
	else:
		raise TypeError(query)

def construct_payload(content):
	str_payload = "{"
	if "so" in content:
		str_payload += '"so":' + str(content["so"])
	if "co" in content:
		str_payload += "," + '"co":' + str(content["co"])
	if "fd" in content:
		str_payload += "," + '"fd":' + str(content["fd"])
	if "frame" in content:
		str_payload += '"frame":' + str(content["frame"])
	if "lo" in content:
		str_payload += "," + '"lo":' + str(content["lo"])
	if "lt" in content:
		str_payload += "," + '"lt":' + str(content["lt"])
	if "na" in content:
		str_payload += "," + '"na":"' + content["na"] + '"'
	if "mt" in content:
		str_payload += '"mt":' + str(content["mt"])
	if "wi" in content:
		str_payload += "," + '"wi":' + str(content["wi"])
	if "ns" in content:
		str_payload += '"ns":' + str(content["ns"])
	return str_payload + "}"


def clean_payload(content):
	start_obj = content.find('{')
	start_array = content.find('[')
	end_obj = content.rfind('}')
	end_array = content.rfind(']')
	start = 0
	end = len(content)
	if start_obj==-1 and start_array!=-1:
		start = start_array
	elif start_obj!=-1 and start_array==-1:
		start = start_obj
	else:
		start = min(start_obj,start_array)

	if end_obj==-1 and end_array!=-1:
		end = end_array+1
	elif end_obj!=-1 and end_array==-1:
		end = end_obj+1
	else:
		end = max(end_obj,end_array)+1

	return filter(lambda x: x in string.printable, content[start:end])