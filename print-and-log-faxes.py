#!/usr/bin/env python
"""
Get inbound faxes, print them, log them.

Get outbound faxes, log them.

Author: Nick Semenkovich <semenko@alum.mit.edu>
License: MIT

This is a hackjob and could be trivially optimized (and hasn't been tested). You've been warned.
"""

import ConfigParser
import pickle
import subprocess
from os import mkdir
from interfax import client
from sys import stderr

print("Getting credentials.")
config = ConfigParser.ConfigParser()
config.read('.auth')

username = config.get('interfax', 'username', 0)
password = config.get('interfax', 'password', 0)

print("Getting inbound/outbound cache...")
try:
     pkl_file = open('.pickle-cache', 'rb')
     inbound_cache = pickle.load(pkl_file)
     while len(inbound_cache) > 20:
          inbound_cache.pop()
except IOError:
     print("\tNo cache found, creating new one.")
     inbound_cache = []

print("Connecting to interfax.")
c = client.InterFaxClient(username, password)

##########
# Inbound faxes
##########

print("Getting 20 most recent inbound faxes...")
in_result = c.getList('AllMessages', 20)
if in_result[0] != 0:
     print >> stderr, "ERROR: Inbound return code %d" % in_result[0]
     exit()
print('GetList returned with %d items' % (len(in_result[1])))

try:
     # This is all on a ram drive for security.
     mkdir("inbound")
except OSError:
     pass

# Loop over inbound faxes
in_log = open('inbound_fax_log.txt', 'w')
for in_item in reversed(in_result[1]):
     # Sanity check
     assert(int(in_item[0]) == in_item[0])

     if in_item[0] not in inbound_cache:
          inbound_cache.insert(0, in_item[0])

          # "\nmessageId: %d\nphoneNumber: %s\nremoteCSID: %s\nmessageStatus: %d\npages: %d\nmessageSize: %d\nmessageType: %d\nreceiveTime: %s\ncallerID: %s\nmessageRecodingDuration: %d"
          dl_return_code = c.getImageChunk(in_item[0], True, in_item[5], 0, "inbound/%d.pdf" % in_item[0] )          

          if dl_return_code == 0:
               print("*** Printing %d" % (in_item[0]))
               ### Call lpr and print
               # retcode = subprocess.call(['lpr', '-P', 'Brother_MFC-8910DW', 'inbound/%d.pdf' % in_item[0]])
               if retcode < 0:
                    print >>sys.stderr, "Printing error, child was terminated by signal", -retcode
          else:
               print("Error downloading message %d, code: %d" % (in_item[0], dl_return_code))

     # Write the log of inbound faxes.
     t = in_item[7]
     rcv_time = "%d/%d/%d %d:%d" % (t[1], t[2], t[0], t[3], t[4])  # Meh, strftime lazy. 
     print >> in_log , "%s> From: %s (%s), Pages: %d, Message ID: %d" % (rcv_time, filter(str.isalnum, in_item[8]), filter(str.isalnum, in_item[2]), in_item[4], in_item[0])

in_log.close()

# Save the printed cache
pickle.dump(inbound_cache, open('.pickle-cache', 'w'))

#############
# Outbound faxes
#############

# Get the last 100 outbound faxes (with ID less than 9999...), really weird interfax API ...
out_result = c.faxQuery( 'LT', 999999999, 100)
if out_result[0] != 0:
     print >> stderr, "ERROR: OUTbound return code %d" % in_result[0]
     exit()
print('FaxQuery returned with %d items' % (len(out_result[1])))

# Save those to our log
out_log = open('outbound_fax_log.txt', 'w')
for out_item in out_result[1]:
     # "\nparentTxId: %d\ntxId: %d\nsubmitTime: %s\npostponeTime: %s\ncompletionTime: %s\nuserId: %s\ncontact: %s\njobId: %s\ndestinationFax: %s\nreplyEmail: %s\nremoteCSID: %s\npagesSent: %s\nstatus: %d\nduration: %d\nsubject: %s\npagesSubmitted: %d\nsenderCSID: %s\npriority: %d\nunits: %d\ncostPerUnit: %d\npageSize: %s\npageOrientation: %s\npageResolution: %s\nrenderingQuality: %s\npageHeader: %s\nretriesToPerform: %d\ntrialsPerformed: %d" % currItem

     t = out_item[2]  # Submitted time.
     rcv_time = "%d/%d/%d %d:%d" % (t[1], t[2], t[0], t[3], t[4]) # Really, strftime could go here...

     status_code = int(out_item[12])
     if status_code == 0:
          status = "Ok"
     elif status_code < 0:
          status = "Sending"
     else:
          status = "ERROR! Code: %d" % (status_code)
     
     if out_item[9] == "info@aldinetravel.com":
          from_user = "(machine)"
     else:
          # Get the username.
          from_user = filter(str.isalnum, out_item[9].split('@')[0])

     print >> out_log, "%s> (%s) From: %s, To: %s, Pages: %d, Transaction: %d" % (rcv_time, status, from_user, filter(str.isalnum, out_item[8]), out_item[11], out_item[1])

out_log.close()
