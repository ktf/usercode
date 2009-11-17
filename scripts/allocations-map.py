#!/usr/bin/env python
#
# Generate a picture of the memory usage of an application using the
# igprof-analyse --dump-allocations output.
#
# Each pixel in the image is a PAGESIZE page. Black means that the page is
# unused, white it means that the page is completely used. Gray shades in 
# between are for various degree of utilization.
# Dimensions of the output image
WIDTH=1024
HEIGHT=1024
BITSPERPAGE=12
PAGESIZE=1<<BITSPERPAGE

import sys
import numpy
from optparse import OptionParser
from Image import fromarray, composite, blend
from ImageDraw import ImageDraw
import re
from math import sqrt
from cStringIO import StringIO

# Simple helper function to print final messages and die gracefully.
def die(*statements):
  for s in statements:
    print s
  sys.exit(1)

USAGE="""Syntax: allocations -o <output-image> <input-filename>
"""

# Draws a given allocation at @a pos address of @a size bites in the memory
# map @a data with a given allocation. The @a fill boolean can be used to
# put a given value for each touched page.
def paintAllocation(data, pos, size, fill=0):
  startpage, endpage = pos/PAGESIZE, ((pos+size)/PAGESIZE)+1
  if fill:
    data[startpage:endpage] = fill
    return

  # If the allocation fits on a single page, just add the contribution of 
  # that page.
  if endpage-startpage == 1:
    data[startpage] += size
    return

  # If the allocation spans multiple pages, add the padding contribution
  # and then fill the pages in between (excluding those used for the
  # padding).
  data[startpage] += PAGESIZE - (pos & (PAGESIZE-1))
  data[endpage] += (pos+size) & (PAGESIZE-1)
  data[startpage+1:endpage-1] = PAGESIZE

# List to hold the top ten stacktraces as found at the end of the report.
topTen = [[] for x in xrange(10)]

# Returns (node, symbol, pos, size) from a string of comma separated values.
# In the case the line starts with @ fill in the top 10 list.
def allocationInfo(l):
  i = l.index(",")
  j = i + 1 + l[i+1:].index(",")
  k = j + 1 + l[j+1:].index(",")
  return (int(l[:i], 16), int(l[i+1:j], 16), int(l[j+1:k], 16), int(l[k+1:], 16))

# Parse the final lines in the report which contains stacktraces for the top
# 10 MEM_LIVE call-tree paths.
# The actual format is:
# 
# @(<rank>,<level>)<node>:<symbol>
#
# where:
# 
# * <rank> is the rank of the call tree path (from 0 to 9)
# * <level> is the depth of the entry in the calltree path.
# * <node> is a unique id for the call tree node.
# * <symbol> is the symbol name associated to such node.
def parseStacktrace(l):
  parts = l.split(")", 1)
  rank, level = parts[0][2:].split(",")
  node, symbol = parts[1].split(":", 1)
  topTen[int(rank)].append((int(node, 16), symbol))
  return

# Paints all allocations. Notice that allocations that fit in one page
# and those that fit in more than one are handled differently.
def paintData(data, allocations, nodeAllocations):
  for node, symbol, pos, size in allocations:
    # Actually paint all the allocations on the map.
    startpage, endpage = pos>>BITSPERPAGE, ((pos+size)>>BITSPERPAGE)
    if startpage == endpage:
      data[startpage] += size
    else:
      paintAllocation(data, pos, size)

# Accumulates the different allocations coming from the same node.
def accumulateData(allocations, nodeAllocations):
  for node, symbol, pos, size in allocations:
    # Accumulate cost for each call-tree node.
    nodeAllocations[node].append((pos, size))

def saveImage(data, nodeAllocations, opts):
  global WIDTH
  global HEIGHT
  global PAGESIZE

  # Collapse "step" rows that are completely empty.
  step = 4
  collapser = numpy.zeros(WIDTH*HEIGHT, numpy.uint32)
  for begin, end in ((WIDTH*y, WIDTH*y + WIDTH*step) 
                     for y in xrange(0, HEIGHT, step)):
    if any(data[begin:end]):
      collapser[begin:end] = 1
  data = data.compress(collapser)
  
  # Create the output false colors picture. Rescale the values in the
  # data array so that they are normalised to 245 and convert the array
  # to 8 bit so that it can be easily used with the paletted mode.
  # Notice that we leave the last ten colors (245 - 255) to highlight
  # fragmented memory allocations coming from a unique stacktrace node.
  # Determine the 10 most fragmented allocations coming from the same symbol
  # and highlight the pages they touch.
  # Reshape the array to be bidimensional rather than linear.
  data *= 245
  data /= PAGESIZE
  
  # Calculate an highlight mask to hightlight top MEM_LIVE allocations.
  highlightNode, highlighNodeName = topTen[4][0]
  for (pos, size) in nodeAllocations[highlightNode]:
    paintAllocation(data, pos, size, 246)
  
  WIDTH = int(sqrt(len(data)))
  data = numpy.reshape(data, (len(data)/WIDTH, WIDTH))
  HEIGHT, WIDTH = data.shape
  
  pilImage = fromarray(numpy.array(data, dtype=numpy.uint8), 'P')
  lut = [0,0,0]
  for x in (int(i / 245. * 255.) for i in range(245)):
    lut.extend([x*0.8, x*0.8 , x*0.8])
  # Extra colors are all purple.
  for x in range(10):
    lut.extend([186., 7., 17.])
  
  pilImage.putpalette(lut)
  
  d = ImageDraw(pilImage)
  for c in xrange(256):
    w, h = WIDTH*0.8 / 256, HEIGHT*0.01
    x, y = c * w+WIDTH*0.1, HEIGHT*0.9 - h
    d.rectangle((x, y, x+w, y+h), fill=c)
  pilImage = pilImage.resize((WIDTH*2, HEIGHT*2))
  pilImage.save(opts.output)

def main():
  global WIDTH
  global HEIGHT
  global PAGESIZE
  parser = OptionParser()
  parser.add_option("-o", "--output", dest="output", 
                    default="allocations-map.png")
  parser.add_option("--debug", dest="debug", action="store_true")
  parser.add_option("--entry", dest="entry")
  opts, args = parser.parse_args()

  if len(args) != 1:
    die(USAGE)

  # Create an image, parse the output using a regexp.
  # Accumulate per node information to decide which are the nodes
  # to be highlighted and which not.
  # Split large allocations in pages of PAGESIZE bytes and
  # add contributions to each page accordingly.
  # The allocations list contains elements of the following form:
  #
  # node, symbol, pos, size
  #
  data = numpy.zeros(WIDTH*HEIGHT, numpy.uint32)
  print "Reading file %s" % args[0]
  f = file(args[0], "r")
  allocations = []
  datafile = f.read()
  atIndex = datafile.index("@")
  allocationsFile = StringIO(datafile[:atIndex])
  stackTraceFile = StringIO(datafile[atIndex:])
  print "Done reading"
  allocations = [allocationInfo(l) for l in allocationsFile.readlines()]
  [parseStacktrace(l) for l in stackTraceFile.readlines()]
  # Map which keeps track of the total amount of memory allocated per node.
  nodeAllocations = dict((info[0], []) for info in allocations)

  print "Painting"
  paintData(data, allocations, nodeAllocations)
  accumulateData(allocations, nodeAllocations)
  
  print "Saving image"
  saveImage(data, nodeAllocations, opts)

import cProfile

if __name__ == "__main__":
  if "--debug" in sys.argv:
    cProfile.run('main()')
  else:
    main()