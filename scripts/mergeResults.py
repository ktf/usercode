#!/usr/bin/env python

import re, os
from optparse import OptionParser
from os.path import abspath, join, basename
from math import sqrt
from sys import exit
import sys
import cProfile

meanResults = {}

lineRE = "\s+([0-9]+)\s+\S+\s+\S+\s+([0-9]+)\s+\S+\s+\S+\s+\S+\s+(.*)</(.*)>" #        128   0.06%  27.80%          0   0.00%   6.44% 0x000000004e111b87 _int_malloc+0x1e7</lib/tls/libc-2.3.4.so>

class ResultLine(object):
  def __init__ (self, count, sortCount, error, text):
    self.__count = count
    self.__sortCount = sortCount
    self.__error = error
    self.__text = text
  def count (self):
    return self.__count
  def __repr__ (self):
    return "%s %s %s" % (self.__text, self.__count, self.__error)
  def __cmp__ (self, other):
    return cmp (other.__sortCount, self.__sortCount) or cmp (self.__text, other._ResultLine__text)
  def asList (self, total):
    return [self.__text, str(self.__count), str(self.__count/total*100) , str(self.__error)]
  def asCSV (self, total):
    return [ '"' + self.__text + '"' , str(self.__count), str(self.__count/total*100), str(self.__error)]


class Measurement (object):
  def __init__ (self):
    self.__counts = []
  def addMeasure (self, m):
    self.__counts.append(m)
  def counts(self):
    for c in self.__counts:
      yield c()
  def sortingCounts(self):
    for c in self.__counts:
      yield c.sortCount()
  def average (self):
    return float (sum(self.counts())) / self.N 

  def sortSum(self):
    return float (sum(self.sortingCounts()))

  def sigma(self):
    return sqrt(float (sum([(self.average() - x)**2 for x in self.counts()])) / self.N)
  def dsm(self):
    return self.sigma() / sqrt(self.N)

def getFileList (opts):
  sys.stderr.write("Analyzing the following files: \n")
  results = []
  seriesPath = join (opts.results, opts.series)
  allFiles = os.walk (seriesPath) 
  nodes = [x for x in allFiles]
  for base, dirs, files in nodes:
    for x in [join (base, f) for f in files]:
      if opts.measureType in basename (x):
        results.append (x)
  sys.stderr.write ("\n".join(sorted(results)))
  sys.stderr.write("\n")
  return results 

def totals (results):
  total = 0
  for l in results:
    total += l.count()
  return total

def printCSV (results):
  total = totals(results)
  for l in results:
    print "@".join(l.asCSV(total))

def printHtml (results):
  total = totals(results)
  lines = ["<tr><td>%s</td><tr>" % "<td></td>".join(s.asList(total)) for s in results ]
  print """<table><tr><td>%s</td><tr></tr></table>""" % "\n".join (lines)

def printText (results):
  total = totals(results)
  for l in results:
    a,b,c,d = l.asCSV(total)
    print " ".join([b, d, c+"%", a]) 

def accumulateMax (obj, c0, c1):
  if obj.c0 <= c0:
    obj.c0 = c0
  if obj.c1 <= c1:
    obj.c1 = c1

def accumulateSum (obj, c0, c1):
  obj.c0 += c0
  obj.c1 += c1

def returnCLABEL(obj):
  return obj.label

def returnC0 (obj):
  return obj.c0

def returnC1 (obj):
  return obj.c1

accumulationFunctions = {
"accumulateMax": accumulateMax,
"accumulateSum": accumulateSum
}

algebraicFunctions = {
"x": lambda s, x, y: x(),
"+": lambda s, x, y : x()+y(),
"-": lambda s, x, y : x()-y(),
"*": lambda s, x, y : x()*y(),
"/": lambda s, x, y : x()/y()
}

class Counter:
  def __init__ (self):
    self.c0 = 0
    self.c1 = 0  
    self.label = ""
  def __call__ (self):
    return self.combination(self.o0, self.o1)

  def sortCount (self):
    return self.sortCombination(self.k0, self.k1)

def matchingLines (filename):
  f = open (filename)
  for line in f.xreadlines(): 
    match = re.match (lineRE, line)
    if match:
      c0, c1, s, f = match.groups()
      yield int(c0), int(c1), s, f

class Simplifier(object):
  def __init__ (self, expression):
    self.mergingExpressions = [x for x in self.__createExpressions(expression)]

  def __createExpressions (self, remainingExpression):
    while remainingExpression:
      remainingExpression = remainingExpression.strip(";")
      if remainingExpression[0] != 's':
        sys.stderr.write("Malformend expression")
        exit (1)
      separator = remainingExpression[1]
      remainingExpression=remainingExpression[2:]
      matcher, substitution, remainingExpression = remainingExpression.split (separator, 2)
      yield (re.compile(matcher), substitution)

  def simplify (self, symbol, fname):
    for merger, substitution in self.mergingExpressions:
      match = merger.match(symbol) or merger.match(fname)
      if match:
        return merger.sub (substitution, match.string)
    return symbol
 
PRINT_METHODS = {
"csv": printCSV,
"html": printHtml,
"text": printText
}

def main ():
  parser = OptionParser()
  parser.add_option ("-e", dest="expressions")
  parser.add_option ("-m", dest="maxCount", action="store_true", default=False)
  parser.add_option ("-c", dest="counter", default="0")
  parser.add_option ("-r", dest="results", default=abspath("results"))
  parser.add_option ("-s", dest="series", default="myOutput")
  parser.add_option ("-t", dest="measureType", default="pfmon-itlb")
  parser.add_option ("-v", dest="verbose", action="store_true", default=False)
  parser.add_option ("-o", dest="outputFormat", default="text")
  parser.add_option ("-k", dest="sortKey", default=None)
  parser.add_option ("-l", dest="limitOutput", default=None)
  
  opts, args = parser.parse_args()
  
  if opts.maxCount:
    Counter.accumulate = accumulateMax
  else:
    Counter.accumulate = accumulateSum 

  if opts.sortKey:
    try:
      key = int(opts.sortKey) 
      Counter.k0 = globals()["returnC" + opts.sortKey]
      Counter.k1 = None
      Counter.sortCombination = algebraicFunctions["x"]
    except ValueError,e:
      match = re.match("([0-9])([+-/*])([0-9])",opts.sortKey)
      if not match: 
        sys.stderr.write("Wrong argument %s" % str(opts.sortKey))
        exit (1)
      Counter.k0, Counter.k1 = [globals()["returnC" + match.group(x)] for x in [1,3]]
      Counter.sortCombination  = algebraicFunctions[match.group(2)]
 
  try:
    counter = int(opts.counter)
    Counter.o0 = globals()["returnC" + opts.counter]
    Counter.o1 = None
    Counter.combination = algebraicFunctions["x"]
  except ValueError,e:
    match = re.match("([0-9])([+-/*])([0-9])",opts.counter)
    if not match: 
      sys.stderr.write("Wrong argument %s" % str(opts.counter))
      exit (1)
    Counter.o0, Counter.o1 = [globals()["returnC" + match.group(x)] for x in [1,3]]
    Counter.combination  = algebraicFunctions[match.group(2)]

  if not opts.sortKey:               
    Counter.k0 = Counter.o0          
    Counter.k1 = Counter.o1          
    Counter.sortCombination = Counter.combination

  fileList = getFileList (opts)

  Measurement.N = 0
  simplifier = Simplifier (opts.expressions)
  for filename in fileList:
    count=0
    results = {}
    for c0, c1, symbol, fname in matchingLines(filename):
      report = simplifier.simplify (symbol, fname) 
      if not report in results:
        results[report] = Counter() 
      results[report].accumulate (c0, c1)
      count += 1
    sys.stderr.write(".")
    if count:
      Measurement.N += 1
    for text, count in results.iteritems():
      if not text in meanResults:
        meanResults[text] = Measurement() 
      if opts.verbose: print text, count
      meanResults[text].addMeasure(count)

  finalList = []
  for text, measure in meanResults.iteritems():
    try:
      finalList.append (ResultLine (measure.average(), measure.sortSum(), measure.dsm(), text)) 
    except ZeroDivisionError:
      pass

  finalList.sort ()
  outputFormats = opts.outputFormat.split(",")
  for x in outputFormats:
    PRINT_METHODS[x](finalList[0:(opts.limitOutput and int(opts.limitOutput)) or len(finalList)])

if __name__ == "__main__":
  if "--profile" in sys.argv:
    try:
      cProfile.run("main()", "Foo")
    except KeyboardInterrupt:
      pass
    import pstats
    p= pstats.Stats("Foo")
    p.strip_dirs().sort_stats('cumulative').print_stats(20)
    p.strip_dirs().sort_stats('time').print_stats(20)
    p.strip_dirs().sort_stats('time').print_callers(5)
  else:
    main()
