#!/usr/bin/env python

import sys
from optparse import OptionParser
from os.path import join, exists, basename
from commands import getstatusoutput
from os import unlink

def parseArgs():
  parser = OptionParser()
  parser.add_option("--show-integrated-patches", 
                    action="store_true", 
                    dest="showIntegratedPatches",
                    default=False,
                    help="Shows reports also for patches which already apply.")
  parser.add_option("--no-reset",
                    action="store_false",
                    dest="reset",
                    default=True,
                    help="Do not do `stg status --reset` before applying patches.")
  parser.add_option("--stg-new-patches", "-n",
                    action="store_true",
                    dest="stgNewPatches",
                    default=False,
                    help="Create new patches using `stg new` if the patch still applies.")
  return parser.parse_args()

# FIXME: check for stg.

class GitRepository(object):
  def init(self):
    if exists(".git"):
      return
    error, output = getstatusoutput("git init")
    if error:
      print "Error while initializing repository"
    f = file(".gitignore", "w+")
    f.write("CVS\n.stgit*\n.masked_patches\n.gitignore.*\nUserCode")
    f.close()
    error, output = getstatusoutput("git add .gitignore *")
    if error:
      print "Error while adding files to repository"
    error, output = getstatusoutput("git commit -m'Initial commit'")
    if error:
      print "Error while committing to repository"
    error, output = getstatusoutput("stg init")
    if error:
      print "Error while initializing stg"
  def popAll(self):
    error, output = getstatusoutput("stg pop -a")
    if error:
      print "Error while popping all the patches"
      print output
      sys.exit(1)
  def pushAll(self):
    error, output = getstatusoutput("stg push -a")
    if error:
      print "Error while pushing back the patches"
      sys.exit(1)

  def applied(self):
    error, output = getstatusoutput("stg applied")
    if error:
      print "Error while getting applied patches."
      print output
      sys.exit(1)
    return output.split("\n")

  def show(self, patchName):
    error, output = getstatusoutput("stg show %s" % patchName)
    if error:
      print "Error while showing patch"
      print output
      sys.exit(1)
    return output

  def checkIfApplied(self, patchFilename):
    applied = self.applied()
    patchName = basename(patchFilename)
    if patchName not in applied:
      return False
    print patchName
    oldComplete = self.show(patchName).split("diff",1)
    if len(oldComplete) != 2:
      return False
    old = oldComplete[1].strip()
    new = file(patchFilename).read().split("diff",1)[1].strip()
    
    if not exists(patchFilename):
      print "Patch %s does not exists" % patchFilename
      sys.exit(1)
    if old != new:
      return False
    return True
    
class RepositoryUpdater(object):
  def init(self):
    self.__path = join(basename(__file__), "getTCQueue.py")
    if not exists(self.__path):
      print "Couldn't find helper util getTCQueue.py"
      sys.exit(1)
  def update(self):
    error, output = getstatusoutput(self.__path)
    if error:
      print "Error while updating repository."
      print "Use `stg status --reset` to go back to the previous state."
      print output
      sys.exit(1)

def createStgPatch(patch, directory):
  error, output = getstatusoutput("stg import -n %s --replace %s" % (patch, join(directory, patch)))
  if not error:
    return
  unlink(".stgit-failed.patch")
  error, output = getstatusoutput("patch -f -p1 -i %s" % join (directory, patch))
  if not error:
    print "  ** Migrating patch %s." % patch
  error, output = getstatusoutput("stg refresh")

if __name__ == "__main__":
  opts, args = parseArgs()

  if len(args) == 0:
    print "Please specify a valid comment."
    print "update"
    print "import"
    print "init"
  
  repository = GitRepository()
  if args[0] == "init":
    repository.init()
    sys.exit(0)
  elif args[0] == "update":
    updater = RepositoryUpdater()
    repository.popAll()
    updater.update()
    repository.assimilateChanges()
    repository.pushAll()
    
  maskedPatches = {} 
  if exists(".masked_patches"):
    maskedPatches = eval(open(".masked_patches").read())
  
      
  if opts.reset:
    error, output = getstatusoutput ("stg status --reset")
  for directory in args:
    patches = []
    for line in open(join(directory, "series")).readlines()[1:]:
      patchName = maskedPatches.get(line.strip(), line.strip())
      if patchName:
        patches.append(patchName)
    for patch in patches:
      if repository.checkIfApplied(join(directory, patch)):
        if opts.showIntegratedPatches:
          print "Patch %s is already in the patch queue." % patch 
        continue
      error, reversed = getstatusoutput("patch --dry-run -E -R -f -p1 -i %s" % join (directory, patch))
      if not error:
        if opts.showIntegratedPatches:
          print "Patch %s is already merged." % patch
        continue
        
      error, output = getstatusoutput("patch --dry-run -E -f -p1 -i %s" % join (directory, patch))
      if not error:
        print "Patch %s still applies." % patch
        if opts.stgNewPatches:
          createStgPatch(patch, directory)
        continue

      print "Patch %s does not apply anymore." % patch
      print "  " + "\n  ".join (output.split("\n")[0:10]).strip("\n")
