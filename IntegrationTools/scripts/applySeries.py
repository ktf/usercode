#!/usr/bin/env python

import sys
from optparse import OptionParser
from os.path import join
from commands import getstatusoutput

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

def createStgPatch(patch, directory):
  error, output = getstatusoutput("stg import -n %s --replace %s" % (patch, join(directory, patch)))
  if error:
    print "Error while creating stg patch %s." % patch
    print output
    sys.exit(1)

if __name__ == "__main__":
  opts, args = parseArgs()
  if opts.reset:
    error, output = getstatusoutput ("stg status --reset")
  for directory in args:
    patches = []
    for line in open(join(directory, "series")).readlines()[1:]:
      patches.append(line.strip())
    for patch in patches:
      error, reversed = getstatusoutput("patch --dry-run -R -f -p1 -i %s" % join (directory, patch))
      if not error:
        if opts.showIntegratedPatches:
          print "Patch %s is already applied." % patch
        continue
        
      error, output = getstatusoutput("patch --dry-run -f -p1 -i %s" % join (directory, patch))
      if not error:
        print "Patch %s still applies." % patch
        if opts.stgNewPatches:
          createStgPatch(patch, directory)
        continue

      print "Patch %s does not apply anymore." % patch
      print "  " + "\n  ".join (output.split("\n")[0:10]).strip("\n")
