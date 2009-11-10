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
PAGESIZE=4096

import sys
import numpy
from optparse import OptionParser
from Image import fromarray
from ImageDraw import ImageDraw
import re

def die(*statements):
  for s in statements:
    print s
  sys.exit(1)

USAGE="""Syntax: allocations -o <output-image> <input-filename>
"""

# Returns true if the allocation fits in one single page.
def singlePage(addr, size):
  return (addr / PAGESIZE) == ((addr + size) / PAGESIZE)

# Add a contribution of size `size` to the page 
def addToPixel(data, addr, size):
  pageaddr = (addr / PAGESIZE)
  x, y = (pageaddr % WIDTH), (pageaddr / HEIGHT)
  data[x, y] += size

# Returns the lower / upper boundary of the page containing addr.
def pageLowerBoundary(addr):
  return (addr / PAGESIZE) * PAGESIZE

def pageUpperBoundary(addr):
  return ((addr / PAGESIZE) + 1) * PAGESIZE - 1 

if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-o", "--output", dest="output", 
                    default="allocations-map.png")
  opts, args = parser.parse_args()

  if len(args) != 1:
    die(USAGE)

  # Create an image, parse the output using a regexp.
  # Split large allocations in pages of PAGESIZE bytes and
  # add contributions to each page accordingly.
  data = numpy.zeros((WIDTH,HEIGHT), numpy.uint32)

  lineRE = re.compile("([^,]*),([^,]*):([^,]*),([^,]*)")

  for l in file(sys.argv[1], "r").readlines():
    node, symbol, pos, size = lineRE.match(l).groups()
    size = int(size)
    pos = int(pos, 16)
    
    # If the allocation fits on a single page, just add the contribution of 
    # that page. 
    if singlePage(pos, size):
      addToPixel(data, pos, size)
      continue
    
    # If the allocation spans multiple pages, add the padding contribution
    # and then fill the pages in between (excluding those used for the 
    # padding, hence the +1 -1 in the loop).
    paddingBefore = pageUpperBoundary(pos) - pos
    addToPixel(data, pos, paddingBefore)
    paddingAfter = (pos + size) - pageLowerBoundary(pos + size)
    addToPixel(data, pos + size, paddingAfter)
    
    for x in xrange(((pos / PAGESIZE) + 1) * PAGESIZE,
                    (((pos + size) / PAGESIZE) - 1) * PAGESIZE, 
                    PAGESIZE):
      addToPixel(data, x, PAGESIZE)
  
  # Create the output grayscale picture. Rescale the values in the
  # data array so that they are normalised to 255 and convert the array
  # two 8 bit so that it can be easily used with the paletted mode.
  data *= 255
  data /= PAGESIZE
  data = numpy.transpose(data)
      
  pilImage = fromarray(numpy.array(data, dtype=numpy.uint8), 'P')
  lut = [0,0,0]
  for x in range(255):
    lut.extend([255-x,x,x/2])
  pilImage.putpalette(lut)
  d = ImageDraw(pilImage)
  for c in xrange(256):
    w, h = WIDTH*0.8 / 256, HEIGHT*0.01
    x, y = c * w+WIDTH*0.1, HEIGHT*0.9 - h
    d.rectangle((x, y, x+w, y+h), fill=c)
  pilImage.save(opts.output)
