#!/usr/bin/env python
#
# Simple index generator for igfiles. 
#
from commands import getstatusoutput
from optparse import OptionParser
from subprocess import Popen, PIPE
import os
from os.path import join
from sys import exit
from zipfile import ZipFile

schema = """
create table if not exists files (
  id integer primary key,
  name text unique
);

create table if not exists events (
  id integer primary key,
  number   integer,
  run      integer,
  file     integer,
  ls       integer,
  bx       integer,
  bsc      bool,
  physics  bool,
  tracks   integer,
  triggers integer 
);

create table if not exists triggers (
  id      integer primary key,
  triggered text unique
);
"""

INSERT_FILE = "INSERT INTO files (name) VALUES (\"%s\");"
INSERT_TRIGGER = "INSERT OR IGNORE INTO triggers (triggered) VALUES (\"%s\");"
INSERT_EVENT = """INSERT OR IGNORE INTO events (number, run, file, ls, bx, bsc, physics, tracks, triggers)
                  SELECT %d, %d, files.id, %d, %d, %d, %d, %d, triggers.id
                  FROM files, triggers 
                  WHERE files.name = \"%s\" and triggers.triggered = \"%s\";"""

def listFiles(f):
  ok, txt = getstatusoutput("ls -t " + f)
  return txt.split("\n")

def doQuery(query, database):
  if os.path.exists("/usr/bin/sqlite3"):
    sqlite="/usr/bin/sqlite3"
  else:
    sqlite="/afs/cern.ch/user/e/eulisse/www/bin/sqlite"
  command = "echo '%s' | %s -separator @@@ %s" % (query, sqlite, database)
  ok, out = getstatusoutput("echo '%s' | %s -separator @@@ %s" % (query, sqlite, database))
  if not ok and out: 
    print command
    print out
  return out 

if __name__ == "__main__":
  parser = OptionParser()
  opts, args = parser.parse_args()
  source = None
  dest = None
  print args
  if len(args) != 2:
    exit(1)

  source = args[0]
  dest = args[1]

  doQuery(schema, dest)
  indexedFiles = doQuery('select name from files;', dest)
  print "**", indexedFiles
  todoFiles = [x for x in listFiles(join(source, "*.ig"))
               if x not in indexedFiles]
  count = 0

  for x in todoFiles:
    f = ZipFile(x) 
    events = f.infolist()
    print f.filename
    doQuery(INSERT_FILE % f.filename, dest)
    for e in events:
      HLTTriggers = []
      L1Triggers = []
      TechTriggers = []
      try:
        dummy, event, run = e.filename.split("/")
      except:
        continue
      event = event.split("_")[1]
      run = run.split("_")[1]
      try:
      	obj = eval(f.read(e.filename))
      except:
	pass
      bsc = 0
      physics = 0
      tracks = 0

      for t in obj["Collections"]["L1GtTrigger_V1"]:
        l1name, l1bit, l1value = t
        if l1value:
          L1Triggers.append(l1name)

      for t in obj["Collections"]["TechTrigger_V1"]:
        techbit, techvalue = t
        if techvalue:
          TechTriggers.append(techbit)

      for t in obj["Collections"]["TriggerPaths_V1"]:
        hltname, hltindex, wasrun, accept, error, objects = t 
        if wasrun and accept and not error:
          HLTTriggers.append(hltname)
          if hltname == "HLT_MinBiasBSC":
            bsc = 1 
          elif hltname == "HLT_PhysicsDeclared":
            physics = 1 
      
      if "Tracks_V1" in obj["Collections"]:
        for t in obj["Collections"]["Tracks_V1"]:
          tracks = len(t)
      
      if "Event_V2" in obj["Collections"]:
        for t in obj["Collections"]["Event_V2"]:
          run, event, ls, orbit, bx, time, localtime = t

      if "Event_V1" in obj["Collections"]:
        for t in obj["Collections"]["Event_V1"]:
          run, event, ls, orbit, bx, time = t

      trigs = ", ".join([str(x) for x in HLTTriggers + L1Triggers + TechTriggers])
      doQuery(INSERT_TRIGGER % trigs, dest)
      doQuery(INSERT_EVENT % (event, run, ls, bx, bsc, physics, tracks, f.filename, trigs), dest)
      if physics and bsc:
        print event, run, ls, bx, bsc, physics, tracks

      count += 1
  print count
