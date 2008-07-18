#!/usr/bin/env python

import urllib2
import sys
import re
import thread, threading
from commands import getstatusoutput
from optparse import OptionParser
from time import sleep
from os.path import exists,join

def parseOptions():
  parser = OptionParser()
  parser.add_option("--workers", "-j",
                    dest="workers",
                    default=1,
                    type="int",
                    help="Number of workers to use to download.")
  return parser.parse_args()
  

class DownloadController(object):
  def __init__(self, payloads, totalPackages):
    self.__payloads = payloads
    self.__usedSubsystems = {}
    self.__bigLock = thread.allocate_lock()
    self.__downloaded = 0
    self.__totalPackages = totalPackages
    self.__currentDot = 0

  def getNextPayload(self):
    self.__bigLock.acquire()
    if not self.__payloads:
      self.__bigLock.release()
      return None
    for tag, payload in self.__payloads.iteritems():
      packages, subsystems = payload
      validPayload = True
      for subsystem in subsystems:
        if subsystem in self.__usedSubsystems:
          validPayload = False
          break
      if not validPayload:
        continue
      self.__usedSubsystems.update(subsystems)
      print "Tag %s for packages %s proposed to thread %s" % (tag, " ".join(packages), thread.get_ident())
      self.__payloads.pop(tag)
      self.__bigLock.release()
      return (tag, packages)
    print "Could not find a package to download."
    self.__bigLock.release()
    return ()
        
  def notifyPackagesDone (self, packages):
    self.__bigLock.acquire()
    print "Thread %s done downloading %s" % (thread.get_ident(), " ".join(packages))
    assert(len(packages))
    subsystems = dict([ (p.split("/")[0], 1) for p in packages])
    print subsystems
    for subsystem in subsystems.iterkeys():
      self.__usedSubsystems.pop(subsystem)
    
    self.__downloaded += len(packages)
    completed = int((self.__downloaded*100)/self.__totalPackages)
    for i in range(self.__currentDot, completed):
      sys.stdout.write(".")
      sys.stdout.flush()
    self.__currentDot = max(self.__currentDot, completed)
                  
    self.__bigLock.release()

          

class CvsTagCollectorFetcher(threading.Thread):
  def __init__ (self, controller):
    threading.Thread.__init__(self)
    self.__controller = controller
    self.__starvingCount = 0

  def run (self):
    payload = self.__controller.getNextPayload()
    while payload != None:
      if payload == ():
        if self.__starvingCount > 10:
          print "Worker is starving dying!"
          break
        self.__starvingCount += 1
        sleep(self.__starvingCount/3+1)
        payload = self.__controller.getNextPayload()
        continue
      self.__starvingCount = 0
      tag, packages = payload
      print "Thread %s downloading" % thread.get_ident()
      checkoutPackages = []
      updatePackages = []
      for package in packages:
        if exists(package):
          tagFile = join(package, "CVS/Tag")
          if not exists(tagFile) or open(tagFile).read().strip("NT").strip() != tag:
            print open(tagFile).read().strip("N").strip()
            assert(False)
            updatePackages.append(package)
            continue
          print "Package %s already existing with correct tag" % package
        else:
          checkoutPackages.append(package)
      if checkoutPackages:    
        error, output = getstatusoutput("cvs checkout -r %s %s" % (tag, " ".join(checkoutPackages)))
        if error:
          print output
          sys.exit(1)
      if updatePackages:
        error, output = getstatusoutput("cvs update -r %s %s" % (tag, " ".join(updatePackages)))
        if error:
          print output
          sys.exit(1)

      self.__controller.notifyPackagesDone(packages)
      payload = self.__controller.getNextPayload()
      
if __name__ == "__main__":
  opts, args = parseOptions()
  if not len(args):
    print "Specify a queue."
    sys.exit(1)
  data = urllib2.urlopen("https://cmstags.cern.ch/cgi-bin/CmsTC/CreateTagList?release=%s" % args[0]).read()
  data = re.sub("<.*table.*>", "", data)
  data = re.sub("</*t[rd]>", "", data)
  data = re.sub("[ \t]+", " ", data)
  lines = [line for line in data.split("\n") if line.strip()]
  byPackage = [l.strip().split(" ", 1) for l in lines]
  byTags = [(v,k) for (k,v) in byPackage if k not in ["SCRAMToolbox"]]
  tagCollections = {}
  totalPkgs = 0
  for t,p in byTags:
    if t not in tagCollections:
      tagCollections[t] = ([], {})
    tagCollections[t][0].append(p)
    tagCollections[t][1][p.split("/")[0]] = 1
    totalPkgs += 1
  controller = DownloadController(tagCollections, totalPkgs) 
  for x in xrange(opts.workers):
    worker = CvsTagCollectorFetcher(controller)
    worker.start()
  
  while threading.activeCount() != 1:
    sleep(1)
