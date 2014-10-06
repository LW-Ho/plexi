from exception import FormatError

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