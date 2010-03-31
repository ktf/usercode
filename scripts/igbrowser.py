#!/usr/bin/env python
#
# Simple web service to find the ig files matching event and run number.
#

import cgi
import os
from commands import getstatusoutput
from sys import exit

DB_FILE="/afs/cern.ch/user/i/iguana/www/igbrowser/index.db"

import cgitb

def doQuery(query):
  database=DB_FILE
  if os.path.exists("/usr/bin/sqlite3"):
    sqlite="/usr/bin/sqlite3"
  else:
    sqlite="/afs/cern.ch/user/e/eulisse/www/bin/sqlite"
  err, result = getstatusoutput("echo '%s' | %s -separator @@@ %s" % (query, sqlite, database))
  return [x.split("@@@") for x in result.split("\n") if x]

FIND_TRACKS="select events.run, events.number, events.ls, events.bx, files.name from events, files where events.tracks > 0 and events.file = files.id order by files.id desc limit 50;"
FIND_FILE="select files.name, events.ls, events.bx from events, files where events.run = %s and events.number = %s and events.file = files.id order by events.file desc;"
FIND_RUN_FILE="select files.name from events, files where events.run = %s and events.file = files.id group by files.name order by files.id desc;"

def printPossibleEvents(what, query):
  print """<h2>Events with reconstructed %s</h2>""" % what
  results = doQuery(query)
  if not results:
    print "<h3>No ig files with tracks reconstructed found.</h3>"
    return
  
  lines = "\n".join(["<tr><td>%s</td></tr>" % "</td><td>".join(x) for x in results])
  print """<table border="1px" cellpadding="3" cellspacing="0">
          <tr>
            <th>Run</th><th>Number</th><th>LS</th><th>BX</th><th>File</th>
          <tr>
          %s
          </table>
""" % lines

def printPossibleFiles():
  print "<h2>Last 10 files produced</h2>"
  results = doQuery("select files.name from files order by name desc limit 10;")
  if not results:
    print "<h3>No files found</h3>"
    return
  print "<br>".join([x[0] for x in results])

def printFileSearch(run, event):
  results = doQuery(FIND_FILE % (run, event))
  if not len(results):
    print "<h2>No ig files found for run %s, event %s</h2>" % (run, event)
    return
  print "<h2>Run %s, Event %s is in file%s:</h2>" % (run, event, len(results) > 1 and "s" or "")
  for x in results:
    f, ls, bx = x
    print "%s (LS:%s, BX: %s)" % (f, ls ,bx)

def printRunSearch(run):
  results = doQuery(FIND_RUN_FILE % run)
  if not len(results):
    print "<h2>No ig file found for run %s.</h2>" % run
    return
  print "<h2>Run %s was found in the following files:</h2>" % run
  for f in results:
    print "%s<br>" % f[0]

def printDefaultPage():
  printPossibleEvents("tracks", FIND_TRACKS)
  printPossibleFiles()
  print "</body></html>"
  exit(0)

def cgiReply():
  print "Content-Type: text/html"
  print

  form = cgi.FieldStorage()
  run = form.getvalue("run") or ""
  event = form.getvalue("event") or ""

  print """<html>
           <body>
	   <h2>Search for a given event</h2>
	   <form>
		Run: <input type="text" name="run" value="%s"/>
		Event: <input type="text" name="event" value="%s"/>
		<input type="submit"/>
	   </form>
""" % (run or "", event or "")

  if not run.isdigit() and not event.isdigit():
    printDefaultPage()
  elif not event.isdigit():
    printRunSearch(run)
    printDefaultPage()
  elif not run.isdigit():
    printDefaultPage() 
  else:
    printFileSearch(run, event)
    printDefaultPage()
  print "</body></html>"

if __name__ == "__main__":
  cgiReply()
