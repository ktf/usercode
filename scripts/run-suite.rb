#!/usr/bin/env ruby 
require 'optparse'
require 'fileutils'

cfg_name = "step2_RAW2DIGI_RECO_POSTRECO_ALCA_VALIDATION_STARTUP.py"  
masterOutput = "results"
attempts = 15 
label = "out"
pfmonRuns= { "itlb"=> {UNHALTED_CORE_CYCLES: 5000000,
                     ITLB_MISS_RETIRED: 200},
              "icache"=> {UNHALTED_CORE_CYCLES: 5000000,
                        L1I_MISSES: 2000}}
debug=false
workingArea=""
options = {}
OptionParser.new do |opts|
  opts.banner = "Usage: run-suite.rb [options]"
  opts.on "-l", "--label LABEL", "label to be used" do |x|
    label = x
  end
  opts.on "-n", "--runs AMOUNT", "number of runs" do |x|
    attempts = x
  end
  opts.on "-c", "--cfg CFG", "cmsRun configuration file" do |x|
    cfg_name = x
  end
  opts.on "-w", "--work-area PATH", "CMSSW working area" do |x|
    workingArea="cd #{x}; eval `scram run -sh`"
  end
  opts.on "-m", "--measure NAMES", "Only do the selected measures" do |x|
    wanted = x.split ","
    pfmonRuns.delete_if {|k, v| ! wanted.include? k}
  end
end.parse!
puts workingArea
cmsRunCmd = `#{workingArea};which cmsRun 2>/dev/null`
abort "Could not find cmsRun" if cmsRunCmd.empty?

outputDir = 0.upto(1000000) do |count|
  attempt = File.join masterOutput, label, count.to_s
  break attempt if not File.exist? attempt
end 

FileUtils.mkpath outputDir
File.join outputDir, "execName" do |name|
  File.open(fname, "w") do |f|
    f.write cmsRunCmd
  end
end

pfmonRuns.each do |key, counterDef|
  pfmonCmd = %{#{workingArea}; cd #{Dir.pwd};
    pfmon --resolv --show-time 
    -e#{counterDef.map { |name, period| name }.join ","}
    --long-smpl-periods=#{counterDef.map { |name, period| period }.join ","}
    -- #{cmsRunCmd} #{cfg_name} 2>&1 
  }.each_line.map {|l| l.chomp }.to_a.join

  puts ">> Measuring #{key}"
  0.upto(attempts.to_i).map { |x|
    File.join outputDir, "pfmon-" + key + x.to_s
  }.each do |filename|
    File.open filename, "w" do |f|
      puts "#{pfmonCmd}" if debug
      f.write pfmonCmd
      f.write `#{pfmonCmd}`
    end
  end
end

puts ">> Done. Output can be found in #{outputDir}"
