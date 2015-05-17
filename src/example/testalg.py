__author__ = 'frank'

blacklisted = []
cchannel = 3
cslot = 6
while True:
	#use a wraparound for the matrix coordinate to keep moving through the matrix
	blacklisted.append([(cchannel + 5) % 5, cslot])
	cchannel += 1
	cslot += 1
	if cslot >= 10:
		break

cchannel = 3
cslot = 6
cchannel -= 1
cslot -= 1
while True:
	blacklisted.append([(cchannel + 5) % 5, cslot])
	cchannel -= 1
	cslot -= 1
	if cslot <= 0:
		break
print "done"