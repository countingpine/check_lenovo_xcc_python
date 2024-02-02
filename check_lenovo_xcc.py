#!/usr/bin/env python3
#
# Copyright 2010, Pall Sigurdsson <palli@opensource.is>
#
# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This script is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.	If not, see <http://www.gnu.org/licenses/>.
# About this script
# 
# This script will check the status of a remote Lenovo Enterprise Flex Chassis
# orginal file check_ibm_bladecenter.py renamed and modified by Silvio Erdenberger, 
#
# version 1.4
# * added cpu storage and memory
# * added critical judgment for power and fans
# * support python2.7 and python3.5
#
# version 1.3
# * removed chassis-status,bladehealth,blowers
# * added voltage
# * renamed powermodules -> power
# * TBD temperature review
#
# version 1.2
# changes 
# * renamed --snmp-password to --snmp_apassword
# * fix a wrong validation of Authentication password in the options parameter
# * fix some typo in the help
# * working with XCC: powermodules,system-health,temperature,fans
# * TBD add voltage
# * TBD remove chassis-status,bladehealth,blowers
# 
# version 1.1
# serdenberger@lenovo.com 17.11.2017
# change filename to check_lenovo_flex.py
# there are several changes to the IBM Bladecenter, whic are not compatible
# changes in version 1.1
# * add possibility to a Privacy Password for authPriv in snmp_security_level
# * required parameter depending on --snmp_security_level
# * add authentication encryption and password
# * add privacy encryption and password
#
# powermodules -> adjust to XCC finish
# changed to XCC OID String, tested with SR950 (2/4 PSU), SR630 (2 PSU)
# 
# system-health -> adjust to XCC finish
#  if no error, the message oid don't exist
# changed to XCC OID String, tested with SR950 (2/4 PSU), SR630 (2 PSU)
#
# temperature -> adjust to XCC finish
# changed to XCC OID String, tested with SR950 (2/4 PSU), SR630 (2 PSU)
#
# fans -> adjust to XCC finish 
# changed to XCC OID String, tested with SR950 (2/4 PSU), SR630 (2 PSU)
#  
# voltage -> adjust to XCC finish
# changed to XCC OID String, tested with SR950 (2/4 PSU), SR630 (2 PSU)
#  

# No real need to change anything below here
version="1.4"
ok=0
warning=1
critical=2
unknown=3 
not_present = -1 
exit_status = -1

state = {}
state[not_present] = "Not Present"
state[ok] = "OK"
state[warning] = "Warning"
state[critical] = "Critical"
state[unknown] = "Unknown"

longserviceoutput="\n"
perfdata=""
summary=""
sudo=False

from sys import exit
from sys import argv
from sys import exc_info
from os import getenv,putenv,environ
import subprocess
from logging import Logger
# Init log level to infor
log = Logger(2)
printf = log.info

# Parse some Arguments
from optparse import OptionParser
parser = OptionParser()
parser.add_option("-m","--mode", dest="mode",
	help="Which check mode is in use (power,cpu,storage,system-health,temperature,fans,voltage)")
parser.add_option("-H","--host", dest="host",
	help="Hostname or IP address of the host to check")
parser.add_option("-w","--warning", dest="warning_threshold",
	help="Warning threshold", type="int", default=None)
parser.add_option("-c","--critical", type="int", dest="critical_threshold",
	help="Critical threshold", default=None)
parser.add_option("-e","--exclude", dest="exclude",
	help="Exclude specific object", default=None)
parser.add_option("-v","--snmp_version", dest="snmp_version",
	help="SNMP Version to use (1, 2c or 3)", default="1")
parser.add_option("-u","--snmp_username", dest="snmp_username",
	help="SNMP username (only with SNMP v3)", default=None)
parser.add_option("-C","--snmp_community", dest="snmp_community",
	help="SNMP Community (only with SNMP v1|v2c)", default=None)
parser.add_option("-p","--snmp_apassword", dest="snmp_apassword",
	help="SNMP authentication password (only with SNMP v3)", default=None)
parser.add_option("-a","--snmp_aprotocol", dest="snmp_aprotocol",
	help="SNMP authentication protocol (SHA only with SNMP v3)", default=None)
parser.add_option("-x","--snmp_ppassword", dest="snmp_ppassword",
	help="SNMP privacy password (only with SNMP v3)", default=None)
parser.add_option("-X","--snmp_pprotocol", dest="snmp_pprotocol",
	help="SNMP privacy protocol AES||DES (only with SNMP v3)", default=None)
parser.add_option("-l","--snmp_security_level", dest="snmp_seclevel",
	help="SNMP security level (only with SNMP v3) (noAuthNoPriv|authNoPriv|authPriv)", default=None)
parser.add_option("-t","--snmp_timeout", dest="snmp_timeout",
	help="Timeout in seconds for SNMP", default=10)
parser.add_option("-d","--debug", dest="debug",
	help="Enable debugging (for troubleshooting", action="store_true", default=False)

(opts,args) = parser.parse_args()


if opts.host == None:
	parser.error("Hostname (-H) is required.")
if opts.mode == None:
	parser.error("Mode (--mode) is required.")

snmp_options = ""
def set_snmp_options():
	global snmp_options
	if opts.snmp_version is not None:
		snmp_options = snmp_options + " -v%s" % opts.snmp_version
	if opts.snmp_version == "3":
		if opts.snmp_username is None:
			parser.error("--snmp_username required with --snmp_version=3")
		if opts.snmp_seclevel is None:
			parser.error("--snmp_security_level required with --snmp_version=3")
		if opts.snmp_seclevel == "noAuthNoPriv":
			snmp_options = snmp_options + " -l %s -u %s " % (opts.snmp_seclevel,opts.snmp_username)
		if opts.snmp_seclevel == "authNoPriv":
			if opts.snmp_apassword is None:
				parser.error("--snmp_apassword required with --snmp_version=3")
			if opts.snmp_aprotocol is None:
				parser.error("--snmp_aprotocol required with --snmp_version=3")
			snmp_options = snmp_options + " -l %s -u %s -a %s -A %s " % (opts.snmp_seclevel,opts.snmp_username,opts.snmp_aprotocol,opts.snmp_apassword)
		if opts.snmp_seclevel == "authPriv":
			if opts.snmp_pprotocol is None:
				parser.error("--snmp_pprotocol required with --snmp_version=3")
			if opts.snmp_ppassword is None:
				parser.error("--snmp_ppassword required with --snmp_version=3")
			if opts.snmp_apassword is None:
				parser.error("--snmp_apassword required with --snmp_version=3")
			if opts.snmp_aprotocol is None:
				parser.error("--snmp_aprotocol required with --snmp_version=3")
			snmp_options = snmp_options + " -l %s -u %s -a %s -A %s -x %s -X %s " % (opts.snmp_seclevel,opts.snmp_username,opts.snmp_aprotocol,opts.snmp_apassword,opts.snmp_pprotocol,opts.snmp_ppassword)
	else:
		if opts.snmp_community is None:
			parser.error("--snmp_community is required with --snmp_version=1|2c")
		snmp_options = snmp_options + " -c %s " % opts.snmp_community 
	snmp_options += " -t %s " % (opts.snmp_timeout)

def error(errortext):
		printf ("* Error: %s" % errortext)
		exit(unknown)

def debug( debugtext ):
		if opts.debug:
				printf	(debugtext)

def nagios_status( newStatus ):
	global exit_status
	exit_status = max(exit_status, newStatus)
	return exit_status

'''runCommand: Runs command from the shell prompt. Exit Nagios style if unsuccessful'''
def runCommand(command):
	debug( "Executing: %s" % command )
	proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
	stdout, stderr = proc.communicate('through stdin to stdout')
	if proc.returncode > 0:
		if proc.returncode == 1: # timeout
			printf ("server %s is not accessible at the moment" % opts.host)
		debug ("Error %s: %s\n command was: '%s'" % (proc.returncode,stderr.strip(),command))
		debug("results: %s" % (stdout.strip() ) )
		if proc.returncode == 127: # File not found, lets print path
			path=getenv("PATH")
			printf ("Check if your path is correct %s" % (path))
		if stderr.find('Password:') == 0 and command.find('sudo') == 0:
			printf ("Check if user is in the sudoers file")
		if stderr.find('sorry, you must have a tty to run sudo') == 0 and command.find('sudo') == 0:
			printf ("Please remove 'requiretty' from /etc/sudoers")
		exit(unknown)
	else:
		return stdout

def end():
	global summary
	global longserviceoutput
	global perfdata
	global exit_status
	printf ("%s - %s | %s" % (state[exit_status], summary,perfdata))
	printf (longserviceoutput)
	if exit_status < 0: exit_status = unknown
	exit(exit_status)

def add_perfdata(text):
		global perfdata
		text = text.strip()
		perfdata = perfdata + " %s " % (text)

def add_long(text):
		global longserviceoutput
		longserviceoutput = longserviceoutput + text + '\n'

def add_summary(text):
	global summary
	summary = summary + text

def set_path(path):
	current_path = getenv('PATH')
	if current_path.find('C:\\') > -1: # We are on this platform
		if path == '':
			pass
		else: path = ';' + path
	else:	# Unix/Linux, etc
		if path == '': path = ":/usr/sbin"
		else: path = ':' + path
	current_path = "%s%s" % (current_path,path)
	environ['PATH'] = current_path



def snmpget(oid):
	snmpgetcommand = "snmpget %s %s %s" % (snmp_options,opts.host,oid)
	output = runCommand(snmpgetcommand)
	oid,result = output.strip().split(' = ', 1)
	resultType,resultValue = result.split(': ',1)
	if resultType == 'STRING': # strip quotes of the string
		resultValue = resultValue[1:-1]
	return resultValue

# snmpwalk -v3 -u v3get mgmt-rek-proxy-p02 -A proxy2011 -l authNoPriv 1.3.6.1.4.1.15497
def snmpwalk(base_oid):
	snmpwalkcommand = "snmpwalk %s %s %s" % (snmp_options, opts.host, base_oid)
	output = runCommand(snmpwalkcommand + " " + base_oid)
	return output

def getTable(base_oid):
	myTable = {}
	output = snmpwalk(base_oid)
	for line in output.split('\n'):
		tmp = line.strip().split(' = ', 1)
		if len(tmp) == 2:
			oid,result = tmp
		else:
			result = result + tmp[0]
#			continue
		tmp = result.split(': ',1)
		if len(tmp) > 1:
			resultType,resultValue = tmp[0],tmp[1]
		else:
			resultType = None
			resultValue = tmp[0]
		if resultType == 'STRING': # strip quotes of the string
			resultValue = resultValue[1:-1]
		index = oid.strip().split('.')
		column = int(index.pop())
		row = int(index.pop())
		#if not myTable.has_key(column): myTable[column] = {}
		if column not in myTable: myTable[column] = {}
		myTable[column][row] = resultValue
	return myTable

def check_power():
	 #BASE OID
	 #		#XCC OID
	 #		#			#PWR Mod OID
	powers = getTable('1.3.6.1.4.1.19046.11.1.1.11.2')
	index = 1	# powerIndex
	exists = 2	# powerFruName
	#		# powerPartNumber
	details = 4	# powerFRUNumber
	#		# powerFRUSerialNumber
	status = 6	# powerHealthStatus
	num_ok = 0
	for i in powers.values():
		myIndex = i[index]
		myStatus = i[status]
		myDetails = i[details]
		myExists = i[exists]
		if myIndex == opts.exclude: continue
		if myStatus == "Normal":
			num_ok = num_ok + 1
		elif myStatus == "Warning":
			nagios_status(warning)
			add_summary( '"%s" status "%s". ' % (myExists,myStatus) )
		else:
			nagios_status(critical)
			add_summary( '"%s" status "%s".' % (myExists, myStatus) )
		add_long('Power "%s" status "%s". ' % (myIndex,myStatus) )
	add_summary( "%s out of %s power are healthy" % (num_ok, len(powers) ) )
	add_perfdata( "'Number of power'=%s" % (len(powers) ) )
		
	nagios_status(ok)

def check_fans():
	 #BASE OID
	 #	#XCC OID
	 #	#	#PWR Mod OID
	fans = getTable('1.3.6.1.4.1.19046.11.1.1.3.2.1')
	fanIndex,fanDescr,fanSpeed,fanNonRecovLimitHigh,fanCritLimitHigh,fanNonCritLimitHigh,fanNonRecovLimitLow,fanCritLimitLow,fanNonCritLimitLow,fanHealthStatus = (1,2,3,4,5,6,7,8,9,10)
	num_ok = 0
	for i in fans.values():
		myIndex = i[fanIndex]
		myStatus = i[fanHealthStatus]
		myDescr = i[fanDescr]
		if myIndex == opts.exclude: continue
		if myStatus == "Normal" or myStatus == "Unknown":
			num_ok = num_ok + 1
		elif myStatus == "Warning":
			nagios_status(warning)
			add_summary( 'Fan "%s" status "%s". %s. ' % (myIndex,myStatus,myDescr) )
		else:
			nagios_status(critical)
			add_summary( 'Fan "%s" status "%s". %s. ' % (myIndex, myStatus,myDescr) )
		add_long('Fan "%s" status "%s". %s. %s ' % (myIndex,myStatus,myDescr,i[fanSpeed]) )
	add_summary( "%s out of %s fans are healthy" % (num_ok, len(fans) ) )
	add_perfdata( "'Number of fans'=%s" % (len(fans) ) )

	nagios_status(ok)

def check_systemhealth():
	systemhealthstat = snmpget('1.3.6.1.4.1.19046.11.1.1.4.1.0')
	index,severity,description = (1,2,3)
	# Check overall health
	if systemhealthstat == '255':
		nagios_status(ok)
		add_summary("Server health: OK. ")
	elif systemhealthstat == "2":
		nagios_status(warning)
		add_summary("Non-Critical Error. ")
	elif systemhealthstat == "4":
		nagios_status(critical)
		add_summary("System-Level Error. ")
	elif systemhealthstat == "0":
		nagios_status(critical)
		add_summary("Critical. ")
	else:
		nagios_status(unknown)
		add_summary("Server health unknown (oid 1.3.6.1.4.1.19046.11.1.1.4.1.0 returns %s). " % systemhealthstat)
	if systemhealthstat == "2" or systemhealthstat == "4" or systemhealthstat == "0": 
		summary = getTable('1.3.6.1.4.1.19046.11.1.1.4.2')
		for row in summary.values():
			if row[severity] == 'Good':
				nagios_status(ok)
			elif row[severity] == 'Warning':
				nagios_status(warning)
			else:
				nagios_status(critical)
			text_row_description = row[description]
#			text_row_description = text_row_description.replace(" ", "")
#			text_row_description = text_row_description.decode("hex")
			#add_summary( "[%s] %s " % (row[severity], text_row_description) )
			add_long( "*[%s] %s " % (row[severity], text_row_description) )
	
def check_temperature():
	# set some sensible defaults
	if opts.warning_threshold is None: opts.warning_threshold = 28
	if opts.critical_threshold is None: opts.critical_threshold = 35
								 #BASE OID
								 #			#XCC OID
								 #			#			#Temp OID
	temperatures = getTable("1.3.6.1.4.1.19046.11.1.1.1.2.1")
	tempIndex,tempDescr,tempReading,tempNominalReading,tempNonRecovLimitHigh,tempCritLimitHigh,tempNonCritLimitHigh,tempNonRecovLimitLow,tempCritLimitLow,tempNonCritLimitLow,tempHealthStatus = (1,2,3,4,5,6,7,8,9,10,11)
	num_ok = 0
	for i in temperatures.values():
		myIndex = i[tempIndex]
		myStatus = i[tempHealthStatus]
		myDetails = i[tempDescr]
		myTemp = i[tempReading]
		myTempCritLimitHigh = i[tempCritLimitHigh]
		if myTempCritLimitHigh == "N/A": myTempCritLimitHigh = "" 
		myTempNonCritLimitHigh = i[tempNonCritLimitHigh]
		if myTempNonCritLimitHigh == "N/A": myTempNonCritLimitHigh = "" 
		if myIndex == opts.exclude: continue
		if myStatus != "Normal":
			nagios_status(warning)
			add_summary( 'Temparature "%s" status "%s". %s. ' % (myIndex,myStatus,myDetails) )
		else:
			num_ok = num_ok + 1
		add_long('Temperature "%s" status "%s". %s:	 %s;%s;%s' % (myIndex,myStatus,myDetails,myTemp,myTempNonCritLimitHigh,myTempCritLimitHigh) )
		add_summary( "%s out of %s temperature are healthy" % (num_ok, len(temperatures) ) )
		add_perfdata( "'Number of temperatures'=%s" % (len(temperatures) ) )

		nagios_status(ok)

def check_voltage():
	# voltage test
	voltages = getTable("1.3.6.1.4.1.19046.11.1.1.2.2")
	voltIndex,voltDescr,voltReading,voltNominalReading,voltNonRecovLimitHigh,voltCritLimitHigh,voltNonCritLimitHigh,voltNonRecovLimitLow,voltCritLimitLow,voltNonCritLimitLow,voltHealthStatus = (1,2,3,4,5,6,7,8,9,10,11)
	num_ok = 0
	for i in voltages.values():
		myIndex = i[voltIndex]
		myStatus = i[voltHealthStatus]
		myDescr = i[voltDescr]
		myVolt = i[voltReading]
		myVoltCritLimitHigh = i[voltCritLimitHigh]
		if myVoltCritLimitHigh == "N/A": myVoltCritLimitHigh = ""
		myVoltNonCritLimitHigh = i[voltNonCritLimitHigh]
		if myVoltNonCritLimitHigh == "N/A": myVoltNonCritLimitHigh = ""
		if myIndex == opts.exclude: continue
		if myStatus != "Normal":
			nagios_status(warning)
			add_summary( 'Voltage "%s" status "%s". %s. ' % (myIndex,myStatus,myDescr) )
		else:
			num_ok = num_ok + 1
		add_long('Voltage "%s" status "%s". %s:	 %s;%s;%s' % (myIndex,myStatus,myDescr,myVolt,myVoltNonCritLimitHigh,myVoltCritLimitHigh) )
	add_summary( "%s out of %s voltages are healthy" % (num_ok, len(voltages) ) )
	add_perfdata( "'Number of voltages'=%s" % (len(voltages) ) )

	nagios_status(ok)

def check_cpu():
	cpus = getTable("1.3.6.1.4.1.19046.11.1.1.5.20.1")
	cpuVpdIndex,cpuVpdDescription,cpuVpdSpeed,cpuVpdIdentifier,cpuVpdType,cpuVpdFamily,cpuVpdCores,cpuVpdThreads,cpuVpdVoltage,cpuVpdDataWidth,cpuVpdHealthStatus,cpuVpdCpuModel = (1,2,3,4,5,6,7,8,9,10,11,12)
	num_ok = 0
	for i in cpus.values():
		 myIndex = i[cpuVpdIndex]
		 myStatus = i[cpuVpdHealthStatus]
		 myDescr = i[cpuVpdDescription]
		 if myIndex == opts.exclude: continue
		 if myStatus == "Normal":
			   num_ok = num_ok + 1
		 elif myStatus == "Warning":
			   nagios_status(warning)
		 else:
			   nagios_status(critical)

		 add_long('"%s" status "%s". ' % (myDescr, myStatus) )
	add_summary('%s out of %s CPUs are healthy.' % (num_ok, len(cpus)) )
	add_perfdata("'Number of CPUs'=%s" % (len(cpus)))

	nagios_status(ok)

def check_storage():
	disks = getTable("1.3.6.1.4.1.19046.11.1.1.12.2.1")
	diskIndex,diskFruName,diskHealthStatus = (1,2,3)
	num_ok = 0
	for i in disks.values():
		myIndex = i[diskIndex]
		myFruName = i[diskFruName]
		myStatus = i[diskHealthStatus]
		if myIndex == opts.exclude: continue
		if myStatus == "Normal":
			num_ok = num_ok + 1
		elif myStatus == "Warning":
			nagios_status(warning)
		else:
			nagios_status(critical)
		add_long('Disk "%s" status "%s". ' % (myFruName, myStatus))
	
	add_summary('%s out of %s disks are healthy.' % (num_ok, len(disks)) )
	add_perfdata("'Number of Disk=%s'" % len(disks))
	
	nagios_status(ok)

def check_memory():
	memory = getTable("1.3.6.1.4.1.19046.11.1.1.5.21.1")
	memoryVpdIndex,memoryVpdDescription,memoryVpdPartNumber,memoryVpdFRUSerialNumber,memroyVpdManufactureDate,memoryVpdType,memoryVpdSize,memoryHealthStatus,memoryConfigSpeed,memoryRatedSpeed,memoryLenovoPartNumber = (1,2,3,4,5,6,7,8,9,10,11)
	num_ok = 0
	for i in memory.values():
		 myIndex = i[memoryVpdIndex]
		 myStatus = i[memoryHealthStatus]
		 myDescr = i[memoryVpdDescription]
		 if myIndex == opts.exclude: continue
		 if myStatus == "Normal":
			  num_ok = num_ok + 1
		 elif myStatus == "Warning":
			  nagios_status(warning)
		 else:
			  nagios_status(critical)
		 add_long('"%s" status "%s". ' % (myDescr, myStatus))
	 
	add_summary('%s out of %s memory are healthy.' % (num_ok, len(memory)) )
	add_perfdata("'Number of Memory=%s'" % len(memory))

	nagios_status(ok)

if __name__ == '__main__':
	try:
		set_snmp_options()
		if opts.mode == 'power':
			check_power()
		elif opts.mode == 'system-health':
			check_systemhealth()
		elif opts.mode == 'temperature':
			check_temperature()
		elif opts.mode == 'fans':
			check_fans()
		elif opts.mode == 'voltage':
			check_voltage()
		elif opts.mode == 'cpu':
			check_cpu()
		elif opts.mode == 'storage':
			check_storage()
		elif opts.mode == 'memory':
			check_memory()
		else:
			parser.error("%s is not a valid option for --mode" % opts.mode)
	except:
		#printf ("Unhandled exception while running script " )
		infor = exc_info()
		debug ("%s : %s" % (infor[0], infor[1]))
		exit(unknown)
	end()


