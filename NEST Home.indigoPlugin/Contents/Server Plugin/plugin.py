#! /usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Michael Hesketh - Corporate Chameleon Limited'
############################################################################################
# Copyright (c) 2015, Corporate Chameleon Limited. All rights reserved.
# http://www.corporpatechameleon.co.uk
#
# This plugin is designed to manage multiple NEST Thermostat and NEST Protect devices in a
# single location.  The user must obtain a developers NEST API authorisation code
# and accept terms of service for their online NEST account.
#
# Instructions on how to do this are contained in the README.txt file on the Indigo Support Site
# Thanks to all the people who suffered the Alpha phase:
#   Matt & Jay (of course)
#   Autolog
#   Finkej
#   Parp
#   DU Lou
#   Perry
#   RogueProliferator
#
# Without their testing and great ideas we wouldn't have even reached the Alpha stage!
#
# I'd also like to credit the previous people who took on this project including MAMORE and SM Baker
# who helped me realise that may it was possible for someone who had no experience of Python to
# develop and support this Plugin
#
# This software is provided 'as-is' and may contain bugs at this point
# Use of this software is the responsibility of the user and no claims
# will be accepted for any damage or expenses relating to its use.
#
# Version:      2.0.50 release NEST HOME)
# API Version:  1.0
# Author:       Mike Hesketh
# Released:     31st December 2016
#
# Requirements: Indigo 6.1/API 1.19 or greater
#               Python 2.6 or greater (not tested with Python 3)
#               Internet access
#               Standard python libraries
#
# This code may be freely distributed and used but copyright references must included
# Use of the NEST API is managed by Google, NEST and the code remains their property
# but they allow free commercial & personal use as long as the user agrees to their
# Terms of Service when creating a NEST Developers account.
# these terms can be viewed at https://developer.nest.com/documentation/cloud/tos
#
############################################################################################

import os, sys

# Locate system path
pypath = os.path.realpath(sys.path[0])
sys.path.append(pypath)

# Check environment for indigo and json
try:
    import indigo
except:
    print("This programme must be run from inside Indigo Pro 6.1")
    sys.exit(1)

try:
    import json
except ImportError:
    print "No json library available. I recommend installing either json"
    print "or simplejson."
    sys.exit(1)

try:
    import indigoPluginUpdateChecker

except ImportError:
    indigo.server.log('No update checker installed')
    sys.exit(1)

# Now import the standard python 2.6 libraries that are used
import urllib2
import time
import datetime
import webbrowser
import subprocess
import ast
import traceback
import random
import csv

# Now install TinyDB
import tinydb
from tinydb import TinyDB, where, Query

# Now set up the NEST Thermostat commands
################################################################################
khvacOperationModeEnumToStrMap = {
    indigo.kHvacMode.Cool: u"cool",
    indigo.kHvacMode.Heat: u"heat",
    indigo.kHvacMode.HeatCool: u"heatcool",
    indigo.kHvacMode.Off: u"off"

}

kFanModeEnumToStrMap = {
    indigo.kFanMode.AlwaysOn: u"always on",
    indigo.kFanMode.Auto: u"auto"

}


def _lookupActionStrFromhvacOperationMode(hvacOperationMode):
    return khvacOperationModeEnumToStrMap.get(hvacOperationMode,

                                              u"unknown")


def _lookupActionStrFromFanMode(fanMode):
    return kFanModeEnumToStrMap.get(fanMode,

                                    u"unknown")


##############################
# USER DEFINED FUNCTIONS
#################
global nestDebug, nestShowT, nestShowW, nestShowC
global gFindStuff
global errorFile
global db

# Set nestDebug initially to trap any early issues
nestDebug = True

# Check for version number and adjust error file location accordingly
errorFile = indigo.server.getLogsFolderPath() + "/NESTHome1Errors.log"

gFindStuff = False
global nestTriggerTemp
nestTriggerTemp = 0


def errorHandler(myError):
    global nestDebug, errorFile

    if nestDebug:
        f = open(errorFile, 'a')
        f.write('-' * 80 + '\n')
        f.write('Exception Logged:' + str(time.strftime(time.asctime())) + ' in ' + myError + ' module' + '\n\n')
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=f)
        f.write('-' * 80 + '\n')
        f.close()


def nestTestingEnv(nestTest, nestShowTemp, nestShowWarnings, nestShowChanges):
    global nestDebug, nestShowT, nestShowW, nestShowC

    nestDebug = nestTest
    nestShowT = nestShowTemp
    nestShowW = nestShowWarnings
    nestShowC = nestShowChanges

    return nestDebug


def setupAPI(nestTest):
    # There is an error in the current Google Test Environment where certain fields are available
    # If the user wants to use a test environment to experiment then they must select TEST in the
    # Plugin preferences or an 'index error' will occur
    global nestDebug, nestShowT, nestShowW, nestShowC
    if nestDebug:
        indigo.server.log(u'Setting up the API...')

    # Set up the names of the fields for Protect
    vStatesProtect = []
    vStatesProtect.append("device_id")
    vStatesProtect.append("locale")
    vStatesProtect.append("software_version")
    vStatesProtect.append("name")
    vStatesProtect.append("name_long")
    vStatesProtect.append("is_online")
    vStatesProtect.append("battery_health")
    vStatesProtect.append("co_alarm_state")
    vStatesProtect.append("smoke_alarm_state")
    vStatesProtect.append("is_manual_test_active")
    vStatesProtect.append("last_manual_test_time")
    vStatesProtect.append("ui_color_state")
    vStatesProtect.append("structure_id")
    vStatesProtect.append("last_connection")
    vStatesProtect.append("where_name")

    # Set up the names of the fields for Thermostats
    vStatesThermo = []
    vStatesThermo.append("device_id")
    vStatesThermo.append("locale")
    vStatesThermo.append("software_version")
    vStatesThermo.append("name")
    vStatesThermo.append("name_long")
    vStatesThermo.append("last_connection")  # Listed but not currently in the test API
    vStatesThermo.append("is_online")
    vStatesThermo.append("can_cool")
    vStatesThermo.append("can_heat")
    vStatesThermo.append("is_using_emergency_heat")
    vStatesThermo.append("has_fan")
    vStatesThermo.append("fan_timer_active")
    vStatesThermo.append("fan_timer_timeout")
    vStatesThermo.append("has_leaf")
    vStatesThermo.append("temperature_scale")
    vStatesThermo.append("hvac_mode")
    vStatesThermo.append("target_temperature_f")
    vStatesThermo.append("target_temperature_c")
    vStatesThermo.append("target_temperature_high_f")
    vStatesThermo.append("target_temperature_low_f")
    vStatesThermo.append("target_temperature_high_c")
    vStatesThermo.append("target_temperature_low_c")
    vStatesThermo.append("ambient_temperature_f")
    vStatesThermo.append("ambient_temperature_c")
    vStatesThermo.append("away_temperature_high_f")
    vStatesThermo.append("away_temperature_high_c")
    vStatesThermo.append("away_temperature_low_f")
    vStatesThermo.append("away_temperature_low_c")
    vStatesThermo.append("humidity")  # Not available in Test API system
    vStatesThermo.append("hvac_state")
    vStatesThermo.append("eco_temperature_high_f")
    vStatesThermo.append("eco_temperature_high_c")
    vStatesThermo.append("eco_temperature_low_f")
    vStatesThermo.append("eco_temperature_low_c")
    vStatesThermo.append("locked_temp_min_f")
    vStatesThermo.append("locked_temp_max_f")
    vStatesThermo.append("locked_temp_min_c")
    vStatesThermo.append("locked_temp_max_c")
    vStatesThermo.append("is_locked")
    vStatesThermo.append("previous_hvac_mode")
    vStatesThermo.append("label")
    vStatesThermo.append("where_name")
    vStatesThermo.append("sunlight_correction_enabled")
    vStatesThermo.append("sunlight_correction_active")
    vStatesThermo.append("fan_timer_duration")
    vStatesThermo.append("time_to_target")
    vStatesThermo.append("time_to_target_training")
    vStatesThermo.append("structure_id")

    # Finally create placeholders for the Plugin Configs that are held in the NEST structure
    vPluginOther = []
    vPluginOther.append("nestAway")
    vPluginOther.append("nestHomeName")
    vPluginOther.append("nestCountryCode")
    vPluginOther.append("nestPostcode")
    vPluginOther.append("nestTimeZone")

    vStatesOther = []
    vStatesOther.append("away")
    vStatesOther.append("name")
    vStatesOther.append("country_code")
    vStatesOther.append("postal_code")
    vStatesOther.append("time_zone")

    return vStatesThermo, vStatesProtect, vStatesOther, vPluginOther


def nestCustomAPI(nestTest):
    global nestDebug, nestShowT, nestShowW, nestShowC
    if nestDebug:
        indigo.server.log(u'Setting up the Custom API...')

    # Set up the names of the fields for Protect
    vCustomProtect = []
    vCustomProtect.append("time_since_last_connection")
    vCustomProtect.append("days_since_last_connection")
    vCustomProtect.append("hours_since_last_connection")
    vCustomProtect.append("mins_since_last_connection")
    vCustomProtect.append("seconds_since_last_connection")
    vCustomProtect.append("time_since_last_test")
    vCustomProtect.append("days_since_last_test")
    vCustomProtect.append("days_since_last_warning")
    vCustomProtect.append("time_of_last_warning")
    vCustomProtect.append("time_since_last_warning")
    vCustomProtect.append("days_since_last_emergency")
    vCustomProtect.append("time_of_last_emergency")
    vCustomProtect.append("time_since_last_emergency")
    vCustomProtect.append("last_warning_type")
    vCustomProtect.append("last_emergency_type")

    # Set up the names of the fields for Thermostats
    vCustomThermo = []
    vCustomThermo.append("coolSetpoint_String")
    vCustomThermo.append("heatSetpoint_String")
    vCustomThermo.append("isheating")
    vCustomThermo.append("iscooling")
    vCustomThermo.append("heatOrCool")
    vCustomThermo.append("time_since_last_connection")
    vCustomThermo.append("days_since_last_connection")
    vCustomThermo.append("hours_since_last_connection")
    vCustomThermo.append("mins_since_last_connection")
    vCustomThermo.append("seconds_since_last_connection")
    vCustomProtect.append("nest_client")

    # Finally create placeholders for the Plugin Configs that are held in the NEST structure

    return vCustomThermo, vCustomProtect


def nestTimeConvert(nestLocalTime):
    # Converts time value into an ISO date format and returns it
    nestNow = time.localtime(nestLocalTime)
    nestNow = time.localtime(nestLocalTime - (nestNow[8] * 3600))

    nestString = ''
    for nestTup in range(0, 3):
        nestLead = ''
        if nestNow[nestTup] < 10: nestLead = '0'
        nestString += nestLead + str(nestNow[nestTup]) + '-'
    nestString = nestString[:-1] + "T"
    for nestTup in range(3, 6):
        nestLead = ''
        if nestNow[nestTup] < 10: nestLead = '0'
        nestString += nestLead + str(nestNow[nestTup]) + ':'
    nestString = nestString[:-1]
    nestString += '.000Z'
    return nestString


def nestTimeCalc(nestTime):
    # Calculates time difference between today and nestTime as a str of format 2015-05-22T13:55:22.092Z
    # If no time provided return 0 days 0 hours 0 mins 0 seconds, 0,0,0,0
    if len(nestTime) < 24:
        if nestDebug:
            indigo.server.log(u'Warning - time sent to nestTimeCalc is blank - '
                              u'expected until first warning or emergency on Protect')
        return "No time available", 0, 0, 0, 0

    nestLastTime = time.mktime(time.strptime(nestTime[:-5], "%Y-%m-%dT%H:%M:%S"))
    nestTuple = time.localtime(time.time())
    nestNow = time.time() - (nestTuple[8] * 3600)
    nestTimeDifference = int(nestNow - nestLastTime)
    nestTimeStr = datetime.timedelta(seconds=nestTimeDifference)
    nestTotal = nestTimeStr.seconds
    nestDays = nestTimeStr.days
    nestHours = int(nestTotal / 3600)
    nestMin = int((nestTotal - (nestHours * 3600)) / 60)
    nestSec = nestTotal - (nestMin * 60) - (nestHours * 3600)
    nestTimeTotal = str(nestDays) + ' days ' + str(nestHours) + ' hours ' + str(nestMin) + ' mins ' + str(
        nestSec) + ' seconds'

    return nestTimeTotal, nestDays, nestHours, nestMin, nestSec


def nestUpdateTime(dev):
    global nestDebug, nestShowT, nestShowW, nestShowC
    if nestDebug:
        indigo.server.log(u'Refreshing Times for Custom state temperatures...')

    # Updates all time fields for Nest Devices
    # Thermostat type first
    if dev.deviceTypeId == 'nestThermostat':
        nestLastConnect = nestTimeCalc(dev.states['last_connection'])
        dev.updateStateOnServer('time_since_last_connection', nestLastConnect[0])
        dev.updateStateOnServer('days_since_last_connection', nestLastConnect[1])
        dev.updateStateOnServer('hours_since_last_connection', nestLastConnect[2])
        dev.updateStateOnServer('mins_since_last_connection', nestLastConnect[3])
        dev.updateStateOnServer('seconds_since_last_connection', nestLastConnect[4])

    elif dev.deviceTypeId == 'nestProtect':
        nestLastConnect = nestTimeCalc(dev.states['last_connection'])
        dev.updateStateOnServer('time_since_last_connection', nestLastConnect[0])
        dev.updateStateOnServer('days_since_last_connection', nestLastConnect[1])
        dev.updateStateOnServer('hours_since_last_connection', nestLastConnect[2])
        dev.updateStateOnServer('mins_since_last_connection', nestLastConnect[3])
        dev.updateStateOnServer('seconds_since_last_connection', nestLastConnect[4])

        nestLastConnect = nestTimeCalc(dev.states['last_manual_test_time'])
        dev.updateStateOnServer('time_since_last_test', nestLastConnect[0])
        dev.updateStateOnServer('days_since_last_test', nestLastConnect[1])

        nestLastWarn = nestTimeCalc(dev.states['time_of_last_warning'])
        dev.updateStateOnServer('time_since_last_warning', nestLastWarn[0])
        dev.updateStateOnServer('days_since_last_warning', nestLastWarn[1])

        nestLastEmer = nestTimeCalc(dev.states['time_of_last_emergency'])
        dev.updateStateOnServer('time_since_last_emergency', nestLastEmer[0])
        dev.updateStateOnServer('days_since_last_emergency', nestLastEmer[1])
    else:
        pass

    return True


def nestMapping(nestSecure, nestFirst=False):
    global nestDebug, nestShowT, nestShowW, nestShowC
    if nestDebug:
        indigo.server.log(u'Refreshing NEST map from home.nest.com...')

    # Downloads the current NEST Map for both thermostats and protects
    # As well as all of the current data for parsing

    nestStructureURL = '/structures'
    nestDeviceURL = '/devices'
    nestAPI = 'https://developer-api.nest.com'
    nestDevices = ''
    nestStructures = ''

    #  First the Structure keys and data
    try:

        nestReq = urllib2.Request(nestAPI + nestStructureURL + '?auth=' + nestSecure)
        nestResponse = urllib2.urlopen(nestReq)
        nestStructures = json.loads(nestResponse.read())
        if nestDebug:
            indigo.server.log(u'Secure connection to Nest API devices secured...')

    except:
        # Problems mapping
        errorHandler('nestMapping')
        if nestDebug:
            indigo.server.log(u'Problem accessing NEST API - try again in 60 seconds')
        return False, nestDevices, nestStructures

    #  Now the Device keys and data
    try:
        nestReq = urllib2.Request(nestAPI + nestDeviceURL + '?auth=' + nestSecure)
        nestResponse = urllib2.urlopen(nestReq)
        nestDevices = json.loads(nestResponse.read())
        if nestDebug:
            indigo.server.log(str(nestDevices))
        if nestDebug:
            indigo.server.log(u'Secure connection to Nest API structures secured...')
    except:
        errorHandler('nestMapping')
        if nestDebug:
            indigo.server.log(u'Problem accessing NEST API - try again in 60 seconds')
        return False, nestDevices, nestStructures

    # Allow for 0 Protects or 0 Thermo locations
    try:
        NestThermo = str(len(nestDevices['thermostats'].keys()))
    except:
        NestThermo = 'no'
    try:
        NestProtect = str(len(nestDevices['smoke_co_alarms'].keys()))
    except:
        NestProtect = 'no'

    if nestDebug:
        indigo.server.log('Nest Has detected the following devices...' + NestThermo + ' NEST Thermostats and: '
                          + NestProtect + ' NEST Protects')
    if len(nestDevices) < 1:
        # No devices found
        return False, nestDevices, nestStructures

    # Scan for changes in infrastructure and adjust
    nestDeviceSync(nestDevices)

    # return results or blank structures if failed
    return True, nestDevices, nestStructures


def getDeviceDisplayListId(dev):
    global nestDebug, nestShowT, nestShowW, nestShowC

    try:
        nestDeviceType = dev.deviceTypeId
        if nestDeviceType == 'nestThermostat':
            nestScale = dev.states['temperature_scale']
            nestTemperature = dev.states['ambient_temperature_' + nestScale.lower()]
            nestTempUI = u'' + str(nestTemperature)
            stateKey = u'ambient_temperature_' + nestScale.lower()
            dev.updateStateOnServer(stateKey, nestTempUI, uiValue=u'%s %s' % (nestTempUI, nestScale.upper()))
        elif nestDeviceType == 'nestProtect':
            nestState = u'' + dev.states['ui_color_state'].capitalize()
            stateKey = u'ui_color_state'
            dev.updateStateOnServer(stateKey, nestState, uiValue=nestState)
        elif nestDeviceType == 'nestHomeMaster':
            nestState = u'' + dev.states['nestAway'].capitalize()
            stateKey = u'nestAway'
            dev.updateStateOnServer(stateKey, nestState, uiValue=stateKey.capitalize())
    except:
        errorHandler('getDeviceDisplayListId')


def nestWriteFieldCheck(nestField):
    # Checks if a nestField can be updated (write access granted)
    # If the device is not a thermostat then reject as no fields can be updated
    try:
        nestWriteFields = {}
        nestWriteFields['target_temperature_f'] = 'Thermostat'
        nestWriteFields['target_temperature_c'] = 'Thermostat'
        nestWriteFields['target_temperature_high_f'] = 'Thermostat'
        nestWriteFields['target_temperature_low_f'] = 'Thermostat'
        nestWriteFields['target_temperature_high_c'] = 'Thermostat'
        nestWriteFields['target_temperature_low_c'] = 'Thermostat'
        nestWriteFields['fan_timer_active'] = 'Thermostat'
        nestWriteFields['hvac_mode'] = 'Thermostat'
        nestWriteFields['away'] = 'Thermostat'
    except:
        errorHandler('nestWriteField')

    if nestWriteFields.has_key(nestField):
        # That's field can be updated
        return True
    else:
        return False


def displayMap(nestDev, vStatesThermo, vStatesProtect, vCustomThermo, vCustomProtect):
    global nestDebug, nestShowT, nestShowW, nestShowC

    if len(vStatesProtect) == 0 or len(vStatesThermo) == 0:
        if nestDebug:
            indigo.server.log('NEST Plugin: Terminal error - No API definition found')
        return

    if vStatesThermo == [] or vStatesProtect == []:
        # No devices found
        if nestDebug:
            indigo.server.log(
                u'NEST Plugin - Terminal error no devices found - please check authorisation key and network')
        return

    # Store string for display
    nestOutputThermo = ''
    nestOutputProtect = ''
    nestTabs = ' -> '
    nestProtectCount = 0
    nestThermoCount = 0

    # Get data for each key in turn
    for dev in indigo.devices.iter("self"):
        try:
            if not dev.enabled or not dev.configured or dev.deviceTypeId == 'nestMaster':
                continue

            # Identify device type and get key
            nestDeviceType = dev.deviceTypeId

            if nestDeviceType == 'nestThermostat':
                if nestThermoCount == 0:
                    nestOutputThermo = nestOutputThermo + '\nDETAILED INFORMATION FOR NEST THERMOSTATS' + '\n'
                    nestOutputThermo = nestOutputThermo + '=========================================' + '\n'
                nestThermoCount += 1

            elif nestDeviceType == 'nestProtect':
                if nestProtectCount == 0:
                    nestOutputProtect = nestOutputProtect + '\nDETAILED INFORMATION FOR NEST PROTECTS' + '\n'
                    nestOutputProtect = nestOutputProtect + '======================================' + '\n'
                nestProtectCount += 1

            if nestDeviceType == 'nestThermostat':
                nestOutputThermo = nestOutputThermo + '\nDetail for Nest Thermostat Key: ' + dev.states[
                    'device_id'] + '\n'

            elif nestDeviceType == 'nestProtect':
                nestOutputProtect = nestOutputProtect + '\nDetail for Nest Protect Key: ' + dev.states[
                    'device_id'] + '\n'

            if nestDeviceType == 'nestThermostat':
                nestOutputThermo = nestOutputThermo + '\nStandard States'
                nestOutputThermo = nestOutputThermo + '\n===============\n'

                for vState in range(len(vStatesThermo)):  # The states for the device type
                    try:
                        nestOutputThermo = nestOutputThermo + vStatesThermo[vState] + ":" + nestTabs + str(
                            dev.states[vStatesThermo[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

                nestOutputThermo = nestOutputThermo + '\nCustom States'
                nestOutputThermo = nestOutputThermo + '\n=============\n'

                for vState in range(len(vCustomThermo)):  # Finally the custom states for the device type
                    try:
                        nestOutputThermo = nestOutputThermo + vCustomThermo[vState] + ":" + nestTabs + str(
                            dev.states[vCustomThermo[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

            elif nestDeviceType == 'nestProtect':
                nestOutputProtect = nestOutputProtect + '\nStandard States'
                nestOutputProtect = nestOutputProtect + '\n===============\n'

                for vState in range(len(vStatesProtect)):  # The states for the device type
                    try:
                        nestOutputProtect = nestOutputProtect + vStatesProtect[vState] + ":" + nestTabs + str(
                            dev.states[vStatesProtect[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

                nestOutputProtect = nestOutputProtect + '\nCustom States'
                nestOutputProtect = nestOutputProtect + '\n=============\n'

                for vState in range(len(vCustomProtect)):  # Finally the custom states for the device type
                    try:
                        nestOutputProtect = nestOutputProtect + vCustomProtect[vState] + ":" + nestTabs + str(
                            dev.states[vCustomProtect[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue
        except:
            errorHandler('displayMap')

    # Other bits of information are not displayed at this time (e.g. Postal Code)
    # Now Print to log
    nestOutput = ''
    if len(nestOutputThermo) > 0:
        nestOutput = '\n' + nestOutputThermo

    if len(nestOutputProtect) > 0:
        nestOutput = nestOutput + '\n' + nestOutputProtect

    if len(nestOutputThermo) > 0 or len(nestOutputProtect) > 0:
        indigo.server.log(nestOutput)

    return


def printMap(nestDev, vStatesThermo, vStatesProtect, vCustomThermo, vCustomProtect, nestFolder):
    global nestDebug, nestShowT, nestShowW, nestShowC

    if len(vStatesProtect) == 0 or len(vStatesThermo) == 0:
        if nestDebug:
            indigo.server.log('NEST Plugin: Terminal error - No API definition found')
        sys.exit(1)

    if nestDev == {}:
        # No devices found
        if nestDebug:
            indigo.server.log(u'NEST Plugin: Terminal error - No API definition found')
        sys.exit(1)

    # Open a file
    nestTime = str(indigo.server.getTime())

    f = open(nestFolder + '/NestMap ' + nestTime + '.txt', mode='w+')
    if nestShowC:
        indigo.server.log("Creating NestMap.txt")

    # Store string for display
    nestOutputThermo = ''
    nestOutputProtect = ''
    nestTabs = ' -> '
    nestProtectCount = 0
    nestThermoCount = 0

    # Get data for each key in turn
    for dev in indigo.devices.iter("self"):

        try:
            if not dev.enabled or not dev.configured or dev.deviceTypeId == 'nestMaster':
                continue

            # Identify device type and get key
            nestDeviceType = dev.deviceTypeId

            if nestDeviceType == 'nestThermostat':
                if nestThermoCount == 0:
                    nestOutputThermo = nestOutputThermo + '\nDETAILED INFORMATION FOR NEST THERMOSTATS' + '\n'
                    nestOutputThermo = nestOutputThermo + '=========================================' + '\n'
                nestThermoCount += 1

            elif nestDeviceType == 'nestProtect':
                if nestProtectCount == 0:
                    nestOutputProtect = nestOutputProtect + '\nDETAILED INFORMATION FOR NEST PROTECTS' + '\n'
                    nestOutputProtect = nestOutputProtect + '======================================' + '\n'
                nestProtectCount += 1

            if nestDeviceType == 'nestThermostat':
                nestOutputThermo = nestOutputThermo + '\nDetail for Nest Thermostat Key: ' + dev.states[
                    'device_id'] + '\n'

            elif nestDeviceType == 'nestProtect':
                nestOutputProtect = nestOutputProtect + '\nDetail for Nest Protect Key: ' + dev.states[
                    'device_id'] + '\n'

            if nestDeviceType == 'nestThermostat':
                nestOutputThermo = nestOutputThermo + '\nStandard States'
                nestOutputThermo = nestOutputThermo + '\n===============\n'

                for vState in range(len(vStatesThermo)):  # The states for the device type
                    try:
                        nestOutputThermo = nestOutputThermo + vStatesThermo[vState] + ":" + nestTabs + str(
                            dev.states[vStatesThermo[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

                nestOutputThermo = nestOutputThermo + '\nCustom States'
                nestOutputThermo = nestOutputThermo + '\n=============\n'

                for vState in range(len(vCustomThermo)):  # Finally the custom states for the device type
                    try:
                        nestOutputThermo = nestOutputThermo + vCustomThermo[vState] + ":" + nestTabs + str(
                            dev.states[vCustomThermo[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

            elif nestDeviceType == 'nestProtect':
                nestOutputProtect = nestOutputProtect + '\nStandard States'
                nestOutputProtect = nestOutputProtect + '\n===============\n'

                for vState in range(len(vStatesProtect)):  # The states for the device type
                    try:
                        nestOutputProtect = nestOutputProtect + vStatesProtect[vState] + ":" + nestTabs + str(
                            dev.states[vStatesProtect[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue

                nestOutputProtect = nestOutputProtect + '\nCustom States'
                nestOutputProtect = nestOutputProtect + '\n=============\n'

                for vState in range(len(vCustomProtect)):  # Finally the custom states for the device type
                    try:
                        nestOutputProtect = nestOutputProtect + vCustomProtect[vState] + ":" + nestTabs + str(
                            dev.states[vCustomProtect[vState]]) + '\n'

                    except KeyError:
                        # Move on to the next one
                        continue
        except:
            errorHandler('printMap')

    # Other bits of information are not displayed at this time (e.g. Postal Code)
    # Now Print to log
    nestOutput = ''
    if len(nestOutputThermo) > 0:
        nestOutput = '\n' + nestOutputThermo

    if len(nestOutputProtect) > 0:
        nestOutput = nestOutput + '\n' + nestOutputProtect

    if len(nestOutput) > 0:
        indigo.server.log(nestOutput)
        f.write('\n')
        f.write(nestOutput)
        f.write("\n")

    if nestShowC:
        indigo.server.log("Finished - NestMap.txt")
    f.close()

    return


def refreshNests(nestDev, nestStates, nestProtects, nestFirst=False):
    global nestDebug, nestShowT, nestShowW, nestShowC

    # Refresh all Nest Devices on demand
    # Can only be called once nestMapping is completed
    # nestDev contains all of the latest nestDevice data
    # nestStr contains all of the structure additional data

    if nestDev == {}:
        errorHandler('refreshNests')
        # No devices found
        if nestDebug:
            indigo.server.log(u'NEST refresh - Terminal error no devices found - '
                              'please check authorisation key and network')
        sys.exit(1)

    # We have data so refresh the device states for all devices
    if nestDebug:
        indigo.server.log(u'Refreshing NESTs...')

    for dev in indigo.devices.iter("self"):
        try:
            if not dev.enabled or not dev.configured:
                continue

            # Identify device type and get key
            nestDeviceType = dev.deviceTypeId

            if nestDeviceType == 'nestHomeMaster':
                # This device is refreshed in the actual concurrent tread automatically so move on
                continue

            nestDeviceKey = dev.states['device_id']
            nestDeviceName = str(dev.states['name_long'] + ' ')
            nestWriteField = False

            if nestDeviceType == 'nestThermostat':
                try:
                    # This is a thermostat so use the API fields for that device
                    # Reset number of sensors for current devices in case they've changed in test
                    newProps = dev.pluginProps
                    newProps["NumTemperatureInputs"] = 1
                    newProps["NumHumidityInputs"] = 1
                    dev.replacePluginPropsOnServer(newProps)

                    nestDeviceType = 'thermostats'
                    nestDeviceUi = nestDeviceName.lower()
                    if nestDeviceUi.find('thermostat') == -1:
                        # Prepare Device name for display
                        nestDeviceName = nestDeviceName + 'Thermostat '

                    for vState in range(len(nestStates)):

                        # Update the states for the device type
                        nestField = nestStates[vState]

                        try:
                            nestScale = nestDev[nestDeviceType][nestDeviceKey]['temperature_scale'].lower()
                            nestTempField = 'ambient_temperature_' + nestScale
                            nestTempField1 = 'humidity'
                            nestCurrentValue = dev.states[nestField]
                            nestTempScale = dev.states['temperature_scale'].lower()
                            nestStateValue = nestDev[nestDeviceType][nestDeviceKey][nestField]
                            dev.updateStateOnServer(nestField, value=nestStateValue)

                            if nestField == nestTempField:
                                nestTempValue = nestDev[nestDeviceType][nestDeviceKey][nestTempField]
                                # Update the State UI Field
                                nestUiValue = u'%s %s' % (str(nestTempValue), nestScale.upper())
                                dev.updateStateOnServer("temperatureInput1", value=str(nestTempValue),
                                                        uiValue=nestUiValue)

                            if nestField == nestTempField1:
                                nestHumValue = nestDev[nestDeviceType][nestDeviceKey][nestTempField1]
                                # Update the State UI Field
                                nestUiValue = u'%s ' % (str(nestHumValue))
                                dev.updateStateOnServer("humidityInput1", value=str(nestHumValue), uiValue=nestUiValue)

                            if not nestCurrentValue == nestStateValue and not nestFirst:
                                # Status updated so record in log
                                if nestField.find('temperature') != -1 and nestField.endswith(nestTempScale):
                                    if nestShowT:
                                        indigo.server.log(
                                            nestDeviceName + ' ' + nestField + " updated to " + str(nestStateValue))

                                elif nestField.find('temperature') == -1:
                                    if nestShowC:
                                        indigo.server.log(
                                            nestDeviceName + ' ' + nestField + " updated to " + str(nestStateValue))

                            if nestField == 'hvac_state':
                                # Using the latest version of the client
                                nestClient = 'nest_client'
                                dev.updateStateOnServer(nestClient, value=2)

                        except KeyError:
                            if nestField == 'hvac_state':
                                # Using the old version of the client
                                nestClient = 'nest_client'
                                dev.updateStateOnServer(nestClient, value=1)

                            if nestDebug:
                                indigo.server.log(
                                    u"Warning - couldn't find field:" + nestField + u" on refresh of Thermostat - expected as "
                                                                                    u"fields available depend on NEST equipment")
                            continue

                    # Update the standard fields on the Thermostat (not required on the Protect as it is Custom)
                    nestKeyFieldUpdate(dev)

                    # Now align the Integer Temperature fields and cool/heat point strings
                    refreshIntTemperatures(dev)
                except:
                    errorHandler('refreshNests - Thermo')

            elif nestDeviceType == 'nestProtect':
                try:
                    nestDeviceType = 'smoke_co_alarms'
                    nestDeviceUi = nestDeviceName.lower()
                    if nestDeviceUi.find('protect') == -1:
                        # Prepare Device name for display
                        nestDeviceName = nestDeviceName + 'Protect '

                    for vState in range(len(nestProtects)):
                        # Update the states for the device type
                        try:
                            nestField = nestProtects[vState]
                            nestCurrentValue = dev.states[nestField]
                            nestStateValue = nestDev[nestDeviceType][nestDeviceKey][nestField]
                            dev.updateStateOnServer(nestField, value=nestStateValue)
                        except KeyError:
                            if nestDebug:
                                indigo.server.log(
                                    u"Warning - couldn't find field:" + nestField + u" on refresh of Protect - expected as "
                                                                                    u"fields available depend on NEST equipment")
                            continue

                        # Check Battery States
                        if nestField == 'battery_health':
                            if nestStateValue.lower() != 'ok':
                                dev.updateStateOnServer('battery_alarm_bool', value='true')
                            else:
                                dev.updateStateOnServer('battery_alarm_bool', value='false')

                        if nestField == 'smoke_alarm_state' or nestField == 'co_alarm_state':

                            # First set the boolean field for control page flags
                            if nestField == 'smoke_alarm_state':
                                if nestStateValue.lower() != 'ok':
                                    dev.updateStateOnServer('smoke_alarm_bool', value='true')
                                else:
                                    dev.updateStateOnServer('smoke_alarm_bool', value='false')

                            elif nestField == 'co_alarm_state':
                                if nestStateValue.lower() != 'ok':
                                    dev.updateStateOnServer('co_alarm_bool', value='true')
                                else:
                                    dev.updateStateOnServer('co_alarm_bool', value='false')

                        if not nestCurrentValue == nestStateValue:
                            if type(nestCurrentValue) is unicode:
                                if nestCurrentValue.lower() != nestStateValue.lower():
                                    # Status updated so record in log
                                    # Warning
                                    if nestStateValue.lower() == 'warning':
                                        nestMessage = ''
                                        if dev.states['co_alarm_state'].lower() == 'warning':
                                            dev.updateStateOnServer('last_warning_type', 'CO Alarm')
                                            nestMessage = 'CO Alarm'

                                        if dev.states['smoke_alarm_state'] == 'warning':
                                            if len(nestMessage) == 0:
                                                dev.updateStateOnServer('last_warning_type', 'Smoke Alarm')
                                            else:
                                                dev.updateStateOnServer('last_warning_type',
                                                                        nestMessage + ', Smoke Alarm')

                                        # Record time
                                        nestTime = nestTimeConvert(time.time())
                                        dev.updateStateOnServer('time_of_last_warning', nestTime)

                                    # Emergency
                                    if nestStateValue.lower() == 'emergency':
                                        nestMessage = ''
                                        if dev.states['co_alarm_state'].lower() == 'emergency':
                                            dev.updateStateOnServer('last_emergency_type', 'CO Alarm')
                                            nestMessage = 'CO Alarm'

                                        if dev.states['smoke_alarm_state'] == 'emergency':
                                            if len(nestMessage) == 0:
                                                dev.updateStateOnServer('last_emergency_type', 'Smoke Alarm')
                                            else:
                                                dev.updateStateOnServer('last_emergency_type',
                                                                        nestMessage + ', Smoke Alarm')

                                        # Record time
                                        nestTime = nestTimeConvert(time.time())
                                        dev.updateStateOnServer('time_of_last_emergency', nestTime)

                                    if nestShowC:
                                        indigo.server.log(nestDeviceName + nestField + " updated to " + str(
                                            nestStateValue).capitalize())
                            else:
                                # Status updated so record in log
                                if nestShowC:
                                    indigo.server.log(nestDeviceName + nestField + " updated to " + str(nestStateValue))

                        if nestField == 'ui_color_state':
                            # Update the UI Symbol for the protect
                            if dev.states[nestField].lower() == 'green':
                                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

                            elif dev.states[nestField].lower() == 'yellow':
                                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)

                            else:
                                dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
                except:
                    errorHandler('refreshNests - Protect')

        except:
            errorHandler('refreshNests')

        # Other information held on the device in the PluginConfig file and this is refreshed separately
        ########################################
        getDeviceDisplayListId(dev)

        # Finally the time information
        nestUpdateTime(dev)

    return


def refreshIntTemperatures(dev):
    # Aligns the integer and float temperatures
    # Request from PhilipB

    # Build fields
    vDeviceThermo = []
    vDeviceThermo.append("target_temperature_f")
    vDeviceThermo.append("target_temperature_c")
    vDeviceThermo.append("target_temperature_high_f")
    vDeviceThermo.append("target_temperature_low_f")
    vDeviceThermo.append("target_temperature_high_c")
    vDeviceThermo.append("target_temperature_low_c")
    vDeviceThermo.append("ambient_temperature_f")
    vDeviceThermo.append("ambient_temperature_c")
    vDeviceThermo.append("away_temperature_high_f")
    vDeviceThermo.append("away_temperature_high_c")
    vDeviceThermo.append("away_temperature_low_f")
    vDeviceThermo.append("away_temperature_low_c")

    try:
        for vCurrentDevice in vDeviceThermo:
            dev.updateStateOnServer(vCurrentDevice + '_int', int(dev.states[vCurrentDevice] + 0.5))

        if dev.states['setpointCool'] == 0.0:
            dev.updateStateOnServer('coolSetpoint_String', "")
        else:
            dev.updateStateOnServer('coolSetpoint_String', str(int(dev.states['setpointCool'] + 0.5)))

        if dev.states['setpointHeat'] == 0.0:
            dev.updateStateOnServer('heatSetpoint_String', '')
        else:
            dev.updateStateOnServer('heatSetpoint_String', str(int(dev.states['setpointHeat'] + 0.5)))

        # Now update icons
        nestHvac = dev.states['hvac_mode']
        refreshIcons(dev, nestHvac)
    except:
        errorHandler('refreshIntTemperatures')


def nestKeyFieldUpdate(dev):
    # Maps & updates the key standard thermostat states based on current status
    # HVAC mode (heat, cool, heat-cool or off)
    global nestTriggerTemp

    # First Set the Mode of the HVAC
    nestHvac = dev.states['hvac_mode']
    try:
        # Refresh HVAC state
        if nestHvac == 'heat':
            dev.updateStateOnServer("hvacOperationMode", indigo.kHvacMode.Heat)
        elif nestHvac == 'cool':
            dev.updateStateOnServer("hvacOperationMode", indigo.kHvacMode.Cool)
        elif nestHvac == 'heat-cool':
            dev.updateStateOnServer("hvacOperationMode", indigo.kHvacMode.HeatCool)
        else:
            dev.updateStateOnServer("hvacOperationMode", indigo.kHvacMode.Off)

        # Refresh FAN state
        if dev.states['has_fan'] and dev.states['fan_timer_active']:
            dev.updateStateOnServer("hvacFanMode", indigo.kFanMode.AlwaysOn)
        else:
            dev.updateStateOnServer("hvacFanMode", indigo.kFanMode.Auto)

        # Refresh Setpoint state
        if dev.states['can_cool'] and dev.states['can_heat'] and dev.states['hvac_mode'] == 'heat-cool':
            # Heat/Cool CoolSetPoint
            nestScale = dev.states['temperature_scale'].lower()
            nestField1 = 'target_temperature_high_' + nestScale
            nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
            nestTempCool = float(dev.states[nestField1])
            nestTempHeat = dev.states['target_temperature_low_' + nestScale]
            if nestTempCool - nestTempHeat < 3:
                # Must maintain a 3 degree difference
                dev.updateStateOnServer("setpointHeat", nestTempCool - 3, uiValue=nestTempUI % (nestTempCool - 3))
                dev.states['target_temperature_low_' + nestScale] = nestTempCool - 3
                dev.states['target_temperature_low_' + nestScale + '_int'] = int((nestTempCool - 3) + 0.5)

            # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
            nestField3 = 'ambient_temperature_' + nestScale
            nestAmbient = float(dev.states[nestField3])
            nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_low_' + nestScale])))

            if nestHeatDiff <= nestTriggerTemp:
                dev.updateStateOnServer('heatpointTrigger', value='true')
            else:
                dev.updateStateOnServer('heatpointTrigger', value='false')

            dev.updateStateOnServer("setpointCool", nestTempCool, uiValue=nestTempUI % (nestTempCool))

            # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
            nestField3 = 'ambient_temperature_' + nestScale
            nestAmbient = float(dev.states[nestField3])
            nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_high_' + nestScale])))

            if nestHeatDiff <= nestTriggerTemp:
                dev.updateStateOnServer('coolpointTrigger', value='true')
            else:
                dev.updateStateOnServer('coolpointTrigger', value='false')


            # Heat/Cool HeatSetPoint
            nestField2 = 'target_temperature_low_' + nestScale
            nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
            nestTempHeat = float(dev.states[nestField2])
            nestTempCool = dev.states['target_temperature_high_' + nestScale]

            if nestTempCool - nestTempHeat < 3:
                # Must maintain a 3 degree difference
                dev.updateStateOnServer("setpointCool", nestTempHeat + 3, uiValue=nestTempUI % (nestTempHeat + 3))
                dev.states['target_temperature_high_' + nestScale] = nestTempHeat + 3
                dev.states['target_temperature_high_' + nestScale + '_int'] = int((nestTempHeat + 3) + 0.5)

            # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
            nestField3 = 'ambient_temperature_' + nestScale
            nestAmbient = float(dev.states[nestField3])
            nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_high_' + nestScale])))

            if nestHeatDiff <= nestTriggerTemp:
                dev.updateStateOnServer('coolpointTrigger', value='true')
            else:
                dev.updateStateOnServer('coolpointTrigger', value='false')

            dev.updateStateOnServer("setpointHeat", nestTempHeat, uiValue=nestTempUI % (nestTempHeat))

            # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
            nestField3 = 'ambient_temperature_' + nestScale
            nestAmbient = float(dev.states[nestField3])
            nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_low_' + nestScale])))

            if nestHeatDiff <= nestTriggerTemp:
                dev.updateStateOnServer('heatpointTrigger', value='true')
            else:
                dev.updateStateOnServer('heatpointTrigger', value='false')

        elif dev.states['hvac_mode'] <> 'heat-cool':
            if dev.states['can_cool'] and dev.states['hvac_mode'] == 'cool':
                # Set cool
                nestScale = dev.states['temperature_scale'].lower()
                nestField = 'target_temperature_' + nestScale
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                nestTempValue = float(dev.states[nestField])
                dev.updateStateOnServer("setpointCool", nestTempValue, uiValue=nestTempUI % (nestTempValue))
                dev.updateStateOnServer("setpointHeat", float(0), uiValue=nestTempUI % (float(0)))

                # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
                nestField3 = 'ambient_temperature_' + nestScale
                nestAmbient = float(dev.states[nestField3])
                nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_' + nestScale])))

                if nestHeatDiff <= nestTriggerTemp:
                    dev.updateStateOnServer('targetTrigger', value='true')
                else:
                    dev.updateStateOnServer('targetTrigger', value='false')

            if dev.states['can_heat'] and dev.states['hvac_mode'] == 'heat':
                # Set heat
                nestScale = dev.states['temperature_scale'].lower()
                nestField = 'target_temperature_' + nestScale
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                nestTempValue = float(dev.states[nestField])
                dev.updateStateOnServer("setpointHeat", nestTempValue, uiValue=nestTempUI % (nestTempValue))
                dev.updateStateOnServer("setpointCool", float(0), uiValue=nestTempUI % (float(0)))

                # Set a trigger if we're within nestTrigger degrees of the heatsetpoint
                nestField3 = 'ambient_temperature_' + nestScale
                nestAmbient = float(dev.states[nestField3])
                nestHeatDiff = abs(int(nestAmbient - float(dev.states['target_temperature_' + nestScale])))

                if nestHeatDiff <= nestTriggerTemp:
                    dev.updateStateOnServer('targetTrigger', value='true')
                else:
                    dev.updateStateOnServer('targetTrigger', value='false')

            if dev.states['hvac_mode'] == 'off':
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointHeat", float(0), uiValue=nestTempUI % (float(0)))
                dev.updateStateOnServer("setpointCool", float(0), uiValue=nestTempUI % (float(0)))

            # Set action flag cool or heat
            refreshIcons(dev, nestHvac)

    except:
        errorHandler('nestKeyFieldUpdate')

    return


def refreshIcons(dev, nestHvac):
    # Refreshes the icons in the display to match the current states on the device
    nestCurrentTemp = dev.states['ambient_temperature_' + dev.states['temperature_scale'].lower()]
    nestCool = dev.states[u'setpointCool']
    nestHeat = dev.states[u'setpointHeat']
    nestMode = nestHvac
    # nestState = dev.states['hvac_state'] - not yet available in the UI
    nestHeating = False
    nestCooling = False
    nestClient = dev.states['nest_client']
    if nestClient == 2:
        # Using the latest version of the API so can use realtime hvac_state
        nestState = dev.states['hvac_state']

        if nestMode == 'heat-cool':
            if nestState == 'off':
                # System is idle
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacAutoMode)
                nestHeating = False
                nestCooling = False

            elif nestState == 'heating':
                # Must be heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
                nestHeating = True
                nestCooling = False

            elif nestState == 'cooling':
                # Must be cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCooling)
                nestCooling = True
                nestHeating = False

        elif nestMode == 'cool':
            if nestState == 'cooling':
                # Must be cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCooling)
                nestCooling = True
                nestHeating = False
            else:
                # Not cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCoolMode)
                nestCooling = False
                nestHeating = False

        elif nestMode == 'heat':
            if nestState != 'heating':
                # Not heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeatMode)
                nestCooling = False
                nestHeating = False
            else:
                # Is heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
                nestHeating = True
                nestCooling = False
        else:
            # HVAC is off
            dev.updateStateImageOnServer(indigo.kStateImageSel.HvacOff)
            dev.updateStateOnServer('heatOrCool', 'Off')
            nestHeating = False
            nestCooling = False

    else:
        # Using the old client
        if nestMode == 'heat-cool':
            if nestCurrentTemp >= nestHeat and nestCurrentTemp <= nestCool:
                # System is idle
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacAutoMode)
                nestHeating = False
                nestCooling = False

            elif nestCurrentTemp < nestHeat:
                # Must be heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
                nestHeating = True
                nestCooling = False

            elif nestCurrentTemp > nestCool:
                # Must be cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCooling)
                nestCooling = True
                nestHeating = False

        elif nestMode == 'cool':
            if nestCurrentTemp >= nestCool:
                # Must be cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCooling)
                nestCooling = True
                nestHeating = False
            else:
                # Not cooling
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacCoolMode)
                nestCooling = False
                nestHeating = False

        elif nestMode == 'heat':
            if nestCurrentTemp >= nestHeat:
                # Not heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeatMode)
                nestCooling = False
                nestHeating = False
            else:
                # Is heating
                dev.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
                nestHeating = True
                nestCooling = False
        else:
            # HVAC is off
            dev.updateStateImageOnServer(indigo.kStateImageSel.HvacOff)
            dev.updateStateOnServer('heatOrCool', 'Off')
            nestHeating = False
            nestCooling = False

    if nestHeating:
        dev.updateStateOnServer('isheating', 'Yes')
        dev.updateStateOnServer('heatOrCool', 'Heating')
    else:
        dev.updateStateOnServer('isheating', 'No')

    if nestCooling:
        dev.updateStateOnServer('iscooling', 'Yes')
        dev.updateStateOnServer('heatOrCool', 'Cooling')
    else:
        dev.updateStateOnServer('iscooling', 'No')

    if not nestHeating and not nestCooling and not nestMode == 'off':
        dev.updateStateOnServer('heatOrCool', "Saving Energy")

        return


def nestCreateDevice(nestType, nestKey, nestDev):
    global nestDebug, nestShowT, nestShowW, nestShowC

    # Creates a new device and puts it in the folder NEST Home
    # Check if the folder NEST Home exists
    if not ('NEST Home' in indigo.devices.folders):
        # Create the folder
        nestFolderId = indigo.devices.folder.create("NEST Home")
        nestFolder = nestFolderId.id
    else:
        nestFolder = indigo.devices.folders.getId("NEST Home")

    if nestType == 'master':
        # Special case - create a master device

        nestRandom = str(random.randrange(10, 2000))
        nestName = 'NEST Home Master(' + nestRandom + ')'
        nestDesc = 'Master device provides access to key fields that are held against the whole NEST system - e.g. away'

        # Create Properties Dictionary for Master
        nestMasterDict = {

            'nestAway': u'Home',
            'nestHomeName': u'Home',
            'nestCountryCode': u'GB',
            'nestPostalCode': u'XXXXXX',
            'nestTimeZone': u'Europe/London',
            'nestStructure': u'To be determined'
        }

        nestDeviceType = 'nestHomeMaster'

        # Now create the device
        try:
            nestNewDevice = indigo.device.create(protocol=indigo.kProtocol.Plugin, deviceTypeId=nestDeviceType,
                                                 name=nestName,
                                                 description=nestDesc, folder=nestFolder, props=nestMasterDict)

            nestNewDevice.updateStateOnServer('nestAway', value=u'Home'.capitalize())
            nestNewDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
            indigo.device.displayInRemoteUI(nestNewDevice, value=True)
            indigo.device.enable(nestNewDevice, value=True)

            return True, nestName

        except:
            errorHandler('nestCreateDevice - Master')
            return False, ""

    # Ok let's create a thermostat or protect device
    nestName = nestDev[nestType][nestKey]["name_long"]
    nestDesc = nestType.upper() + " [Add more information here]"
    nestPropsDevice = nestDev[nestType][nestKey]

    # Get the right device ID
    if nestType == 'thermostats':
        nestDeviceType = 'nestThermostat'
    else:
        nestDeviceType = 'nestProtect'

    # Now create the device
    try:
        nestNewDevice = indigo.device.create(protocol=indigo.kProtocol.Plugin, deviceTypeId=nestDeviceType,
                                             name=nestName,
                                             description=nestDesc, folder=nestFolder)


        # Now sync the device states on the server
        nestNewDevice.updateStateOnServer('device_id', value=nestKey)
        if nestDeviceType == 'nestProtect':
            nestNewDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

        elif nestDeviceType == 'nestThermostat':
            newProps = nestNewDevice.pluginProps
            newProps["NumTemperatureInputs"] = 1
            newProps["NumHumidityInputs"] = 1
            nestNewDevice.replacePluginPropsOnServer(newProps)

        # Enable the device
        indigo.device.displayInRemoteUI(nestNewDevice, value=True)
        indigo.device.enable(nestNewDevice, value=True)

        # Refresh fields and icons
        nestUpdate = []
        nestFirst = True
        nestKeyFieldUpdate(nestNewDevice)
        nestFirst = False

        return True, nestName

    except:
        errorHandler('nestCreateDevice - Thermostat or Protect')
        return True, nestName


def nestDeviceSync(nestDev):
    global nestDebug, nestShowT, nestShowW, nestShowC

    # Scan current devices and sync by creating or deleting indigo devices
    nestDeviceTypes = []
    nestDeviceTypes.append('thermostats')
    nestDeviceTypes.append('smoke_co_alarms')
    nestDeviceTypes.append('master')
    for vType in nestDeviceTypes:
        # Look at nest devices one type at a time
        if vType == 'thermostats':
            try:
                for vKey in nestDev[vType].keys():  # Devices found in the type
                    nestFound = False
                    # Does that Thermostat key already exist in the current devices?
                    for dev in indigo.devices.iter('self.nestThermostat'):

                        # Does the device still exist in the data structure?
                        if nestDev[vType].keys().count(dev.states['device_id']) == 0:
                            # Device no longer exists on Nest Home so delete it
                            if nestShowC:
                                indigo.server.log('Thermostat device ' + dev.states['name_long'] + ' deleted')
                            indigo.device.delete(dev)
                            continue

                        if vKey == dev.states['device_id']:
                            # Yes we have that device

                            # Update its fields on the server
                            nestFound = True
                            break
                        else:
                            continue

                    if not nestFound:
                        # Create a thermostat device
                        nestNewDevice = nestCreateDevice(vType, vKey, nestDev)
                        if nestNewDevice[0]:
                            if nestShowC:
                                indigo.server.log('New Thermostat added to indigo: ' + nestNewDevice[1])
                        else:
                            if nestDebug:
                                indigo.server.log(
                                    'Indigo failed to add the Thermostat for key: ' + vKey + ' Name not unique ')
            except:
                if nestDebug:
                    indigo.server.log(
                        'Indigo found no Thermostats - Expected if none installed or failed to access to API')
                continue

        elif vType == 'smoke_co_alarms':
            # Does that Protect key already exist in the current devices?
            try:
                for vKey in nestDev[vType].keys():  # Devices found in the type
                    nestFound = False
                    # Does that key already exist in the current devices?

                    for dev in indigo.devices.iter('self.nestProtect'):

                        #  Is the Protect Device in Nest Home?
                        if nestDev[vType].keys().count(dev.states['device_id']) == 0:
                            # Device no longer exists on Nest Home so delete it
                            if nestShowC:
                                indigo.server.log('Protect device ' + dev.states['name_long'] + ' deleted')
                            indigo.device.delete(dev)
                            continue

                        if vKey == dev.states['device_id']:
                            # Yes we have that device already

                            #  Update its fields on the server
                            nestFound = True
                            break
                        else:
                            continue

                    if not nestFound:
                        # Create a protect device
                        nestNewDevice = nestCreateDevice(vType, vKey, nestDev)

                        if nestNewDevice[0]:
                            if nestShowC:
                                indigo.server.log('New Protect added to indigo: ' + nestNewDevice[1])
                        else:
                            if nestDebug:
                                indigo.server.log(
                                    'Indigo failed to add the Protect device for key: ' + vKey + ' Name not Unique')
            except:
                if nestDebug:
                    indigo.server.log(
                        'Indigo found no Protects - Expected if none installed or failed to access to API')
                continue

        else:
            # Check for a Master Device
            nestFound = False

            # Does that key already exist in the current devices?
            for dev in indigo.devices.iter('self.nestHomeMaster'):
                # Already exists so move on
                nestFound = True

            if not nestFound:
                # Create a master device
                nestNewDevice = nestCreateDevice('master', 'master', 'master')
                if nestNewDevice[0]:
                    if nestShowC:
                        indigo.server.log('New Master NEST device added to indigo: ' + nestNewDevice[1])
                else:
                    if nestDebug:
                        indigo.server.log('Indigo failed to add a NEST Home Master device')


def nestUpdateField(nestSecure, nestDeviceType, nestDeviceKey, nestDeviceName, nestField, nestValue):
    global nestDebug, nestShowT, nestShowW, nestShowC

    # Get the authorisation code and then update NEST
    # Investigating options to use a urllib2 command but need to understand how
    # to manage HTTP 307 redirects.  Curl command works fine
    # Check field is allowed - write access
    nestFieldCheck = nestWriteFieldCheck(nestField)
    try:
        if nestFieldCheck:
            # Ok we can update
            # Changing the AWAY status needs to use a different part of the json - structures not devices

            if nestDeviceType != 'structures':
                # Needs to be set to the devices form
                nestDeviceType = "devices/" + nestDeviceType

            # There are three types of data - string update, value or lowercase boolean
            # The format of the string is -d '{"field_name":"stringValue"}
            # The format of the value/boolean is -d '{"field_name":Value}
            # hvac_mode is the only special case of string
            if nestValue == 'true' or nestValue == 'false':
                nestData = '-d \'{"' + nestField + '":' + str(nestValue) + "}'"

            elif type(nestValue) is str or type(nestValue) is unicode:
                nestData = " -d '{" + '"' + nestField + '":"' + str(nestValue) + "\"}'"

            elif type(nestValue) is int:
                nestValue = float(nestValue)
                nestData = '-d \'{"' + nestField + '":' + str(nestValue) + "}'"
                nestValue = float(nestValue)

            else:
                nestData = '-d \'{"' + nestField + '":' + str(nestValue) + "}'"

            nestUpdate = ''
            nestUpdate = "curl -L -X PUT -H 'Content-Type:application/json' 'https://developer-api.nest.com/" + nestDeviceType
            nestUpdate = nestUpdate + '/' + nestDeviceKey + '?auth=' + nestSecure + "' " + nestData

            url = os.system(nestUpdate)

            return True

        else:
            return False
    except:
        errorHandler('nestDeviceSync')
        if nestDebug:
            indigo.server.log(nestDeviceName.upper() + ':' + nestField + " couldn't be updated")
        return False


################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):

        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.validatePrefsConfigUi(pluginPrefs)
        global nestDebug, nestShowT, nestShowW, nestShowC
        global gFindStuff, nestTriggerTemp, errorFile

        # Set up version checker
        # nestVersionFile = 'https://www.dropbox.com/s/le3hds7xzat3nkc/NESTHomeVersionInfo.html?dl=0'
        # self.updater = indigoPluginUpdateChecker.updateChecker(self, nestVersionFile, 1)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def validatePrefsConfigUi(self, valuesDict):
        errorDict = indigo.Dict()

        if 'nestAuthorisation' in valuesDict:
            if len(valuesDict['nestAuthorisation']) < 100:
                valuesDict['nestAuthorisation'] = 'Please enter valid key'
                # Key is either too short or has not been entered as NEST SPI keys are 146 characters
                errorDict = indigo.Dict()
                errorDict["nestAuthorisation"] = "Invalid NEST API entered (Too short)"
                errorDict["showAlertText"] = "You must obtain a valid NEST API key before installing this plugin"
                return (False, valuesDict, errorDict)

        else:
            # Key is either too short or has not been entered as NEST SPI keys are 146 characters
            errorDict = indigo.Dict()
            errorDict["nestAuthorisation"] = "NEST API Key Missing"
            errorDict["showAlertText"] = "You must obtain a valid NEST API key before installing this plugin"
            valuesDict['nestAuthorisation'] = ''
            return (False, valuesDict, errorDict)

        return (True, valuesDict)

    ########################################
    # Internal utility methods. Some of these are useful to provide
    # a higher-level abstraction for accessing/changing thermostat
    # properties or states.
    ######################

    def _getTempSensorCount(self, dev):
        return 1

    def _getHumiditySensorCount(self, dev):
        return 1

    ######################
    def _changeTempSensorCount(self, dev, count):
        newProps = dev.pluginProps
        newProps["NumTemperatureInputs"] = count
        dev.replacePluginPropsOnServer(newProps)

    def _changeHumiditySensorCount(self, dev, count):
        newProps = dev.pluginProps
        newProps["NumHumidityInputs"] = count
        dev.replacePluginPropsOnServer(newProps)

    def _changeAllTempSensorCounts(self, count):
        for dev in indigo.devices.iter("self.nestThermostat"):
            self._changeTempSensorCount(dev, count)

    def _changeAllHumiditySensorCounts(self, count):
        for dev in indigo.devices.iter("self.nestThermostat"):
            self._changeHumiditySensorCount(dev, count)

    ######################
    def _changeTempSensorValue(self, dev, index, value):
        # Update the temperature value at index. If index is greater than the "NumTemperatureInputs"
        # an error will be displayed in the Event Log "temperature index out-of-range"
        stateKey = u"temperatureInput" + str(index)
        dev.updateStateOnServer(stateKey, value, uiValue="%d F" % (value))
        if nestDebug:
            indigo.server.log(u"\"%s\" called update %s %d" % (dev.name, stateKey, value))

    def _changeHumiditySensorValue(self, dev, index, value):
        # Update the humidity value at index. If index is greater than the "NumHumidityInputs"
        # an error will be displayed in the Event Log "humidity index out-of-range"
        stateKey = u"humidityInput1"
        dev.updateStateOnServer(stateKey, dev.states['humidity'], uiValue="%d F" % (value))
        if nestDebug:
            indigo.server.log(u"\"%s\" called update %s %d" % (dev.name, stateKey, value))

    # Now define the key functions used to manage Nest Thermostat and Protect devices
    ######################
    # Poll all of the states from the thermostat and pass new values to
    # Indigo Server.
    def _refreshStatesFromHardware(self, dev):
        # Send status updates to the indigo log
        if nestDebug:
            indigo.server.log(u"states check called")

        # Nest Plugin Configurations
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])

        # Now complete an initial refresh of the API and devices
        nestAPI = setupAPI(False)
        nestMap = nestMapping(nestSecure)
        try:
            if nestMap[0]:
                refreshNests(nestMap[1], nestAPI[0], nestAPI[1])
            else:
                if nestDebug:
                    indigo.server.log(u'Failed to access API - REFRESH HARDWARE')
        except:
            errorHandler('refreshStatesFromHardware')

    ######################
    # Process action request from Indigo Server to change main thermostat's main mode.
    def _handleChangehvacOperationModeAction(self, dev, newhvacOperationMode):

        # Nest Plugin Configurations
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])
        actionStr = _lookupActionStrFromhvacOperationMode(newhvacOperationMode)

        # Filter out incorrect actions for set up
        if actionStr == 'heatcool':
            if not (dev.states['can_cool'] and dev.states['can_heat']):
                return False
        if actionStr == 'cool':
            if not dev.states['can_cool']:
                return False
        if actionStr == 'heat':
            if not dev.states['can_heat']:
                return False

        if actionStr == 'heatcool':
            # Allow for difference in terminology NEST v Indigo
            actionStr = 'heat-cool'

        sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'], dev.states['name_long'],
                                      'hvac_mode', actionStr)

        if sendSuccess:
            # If success then log that the command was successfully sent
            if nestShowC:
                indigo.server.log(u"sent \"%s\" mode change to %s" % (dev.name, actionStr))

            # And then tell the Indigo Server to update the state.
            if actionStr == 'heatcool':
                #  Revert to NEST Terminology
                actionStr = 'heat-cool'

            if "hvac_mode" in dev.states:
                dev.updateStateOnServer("hvac_mode", actionStr)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                if nestDebug:
                    indigo.server.log(u"send \"%s\" mode change to %s failed" % (dev.name, actionStr), isError=True)

        return True

    ######################
    # Process action request from Indigo Server to change thermostat's fan mode.
    def _handleChangeFanModeAction(self, dev, newFanMode):

        # Nest Plugin Configurations
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])
        actionStr = _lookupActionStrFromFanMode(newFanMode)

        # Allow for difference in terminology NEST v Indigo
        if actionStr == 'always on':
            actionNest = "true"
        else:
            actionNest = "false"

        sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'], dev.states['name_long'],
                                      'fan_timer_active', actionNest)
        if sendSuccess:
            # If success then log that the command was successfully sent.
            if nestShowC:
                self.debugLog(u"sent \"%s\" fan mode change to %s" % (dev.states['name_long'], actionStr))

            # And then tell the Indigo Server to update the state.
            if "fan_timer_active" in dev.states:
                dev.updateStateOnServer("fan_timer_active", actionNest)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                if nestDebug:
                    self.debugLog(u"send \"%s\" fan mode change to %s failed" % (dev.states['name_long'], actionStr),
                                  isError=True)

    ######################
    # Process action request from Indigo Server to change a cool/heat setpoint.
    def _handleChangeSetpointAction(self, dev, newSetpoint, logActionName, stateKey):

        # Nest Plugin Configurations
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])

        # First get the scale that's being used
        nestScale = dev.states['temperature_scale']  # C or F
        nestMode = dev.states['hvac_mode']

        if nestScale.upper() == 'F':
            nestMax = 90
            nestMin = 50
        else:
            nestMax = 32
            nestMin = 9

            # Now check values and adjust to max or min values
            if newSetpoint < nestMin:
                newSetpoint = nestMin
            elif newSetpoint > nestMax:
                newSetpoint = nestMax

                # Now change the set point check which fields to use
                # If hvac_mode is heat-cool then we have to use the fields temperature_high or temperature_low
                # otherwise we use target_temperature
                # We also need to build the field depending on the scale used

        if stateKey == u"setpointCool":
            if nestMode == 'heat-cool':
                nestField = 'target_temperature_high_' + nestScale.lower()
                sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'],
                                              dev.states['name_long'],
                                              nestField, newSetpoint)
            else:
                nestField = 'target_temperature_' + nestScale.lower()
                sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'],
                                              dev.states['name_long'],
                                              nestField, newSetpoint)
        elif stateKey == u"setpointHeat":
            if nestMode == 'heat-cool':
                nestField = 'target_temperature_low_' + nestScale.lower()
                sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'],
                                              dev.states['name_long'],
                                              nestField, newSetpoint)
            else:
                nestField = 'target_temperature_' + nestScale.lower()
                sendSuccess = nestUpdateField(nestSecure, 'thermostats', dev.states['device_id'],
                                              dev.states['name_long'],
                                              nestField, newSetpoint)

        if sendSuccess:
            # If success then log that the command was successfully sent.
            if nestShowC:
                indigo.server.log(u"sent \"%s\" %s to %.1f " % (dev.name, logActionName, newSetpoint))

            # And then tell the Indigo Server to update the states
            if nestField in dev.states:
                dev.updateStateOnServer(nestField, newSetpoint)
                dev.updateStateOnServer(nestField + '_int', int(newSetpoint + 0.5))

            else:
                # Else log failure but do NOT update state on Indigo Server.
                if nestDebug:
                    self.debugLog(u"send \"%s\" %s to %.1f  failed" % (dev.name, logActionName, newSetpoint),
                                  isError=True)

    def startup(self):
        global db

        if self.pluginPrefs.get('checkBoxDebug', False):
            indigo.server.log(u"startup called")
        try:
            self.pluginPrefs.get('showTemps', True)
            self.pluginPrefs['helpAPI'] = 'false'
            self.pluginPrefs['helpAPI2'] = 'false'
            self.pluginPrefs['nestPIN'] = ''
            self.nestDataManagement = self.pluginPrefs.get('nestData', 'false')
            self.nestStorage = self.pluginPrefs.get('nestTxt', '')
            self.nestDataChange = False

            if self.nestDataManagement and len(self.nestStorage) != 0:
                indigo.devices.subscribeToChanges()

                # Tracking is on so switch on the db file tracking
                indigo.server.log('** Data Tracking Online **')
                try:
                    # Open the current tracking database
                    db = TinyDB(self.nestStorage + '/NESTdb.track')
                    self.nestDataChange = True

                except:
                    errorHandler('startup - TinyDB access failed')
            else:
                # Tracking is off so switch off the db file tracking
                indigo.server.log('** Data Tracking Offline **')

            #self.updater.checkVersionPoll()

        except:
            errorHandler('startUp')
            if self.pluginPrefs.get('checkBoxDebug', False):
                self.errorLog(u"Update checker error.")

        for dev in indigo.devices.itervalues("self"):
            dev.stateListOrDisplayStateIdChanged()

    def shutdown(self):
        indigo.server.log(u"shutdown called")

    ########################################
    def runConcurrentThread(self):
        # Get the most current information
        # Validate preferences exist
        global gFindStuff, nestTriggerTemp, nestShowT, nestShowW, nestShowC, errorFile, db

        nestFirst = True

        nestValidAPI = False
        while not nestValidAPI:
            nestSecure = self.pluginPrefs.get('nestAuthorisation', '')
            if len(nestSecure) > 100:
                nestValidAPI = True
            else:
                self.sleep(5)

        self.nestDataManagement = self.pluginPrefs.get('nestData', 'false')
        self.nestStorage = self.pluginPrefs.get('nestTxt', '/Users')

        # Empty log
        iLogTime = 3600
        f = open(errorFile, 'w')
        f.write('#' * 80 + '\n')
        f.write('New Log:' + str(time.strftime(time.asctime())) + '\n')
        f.write('#' * 80 + '\n')
        f.close()
        logTimeNextReset = time.time() + int(iLogTime)

        while True:
            # Nest Plugin Configurations
            nestSecure = self.pluginPrefs.get('nestAuthorisation', "")
            nestTimer = int(self.pluginPrefs.get('nestTimer', "60"))
            nestTest = self.pluginPrefs.get('checkboxDebug', False)
            nestShowT = self.pluginPrefs.get('showTemps', True)
            nestShowW = self.pluginPrefs.get('showWarnings', True)
            nestShowC = self.pluginPrefs.get('showChanges', True)
            nestTests = nestTestingEnv(nestTest, nestShowT, nestShowW, nestShowC)
            self.nestDataManagement = self.pluginPrefs.get('nestData', 'false')
            self.nestStorage = self.pluginPrefs.get('nestTxt', '/Users')
            nestCheckForUpdates = self.pluginPrefs.get('updaterEmailsEnabled', True)
            nestTrig = self.pluginPrefs.get('nestTriggerSetpoints', "5")
            nestTriggerTemp = int(nestTrig)
            # if nestCheckForUpdates:
            #     self.updater.checkVersionPoll()

            # Is tracking now on?
            if self.nestDataManagement and not self.nestDataChange:
                # Logging has been switched on
                indigo.devices.subscribeToChanges()
                try:
                    # Open the current tracking database
                    db = TinyDB(self.nestStorage + '/NESTdb.track')
                    self.nestDataChange = True

                except:
                    errorHandler('runConcurrent - TinyDB access failed')

            if not self.nestDataManagement and self.nestDataChange:
                db.close()

                # Tracking is off so switch off the db file tracking
                indigo.server.log('** Data Tracking Offline **')
                self.nestDataChange = False

            # Reset the log?
            if logTimeNextReset < time.time():
                # Reset log
                # Empty log
                f = open(errorFile, 'w')
                f.write('#' * 80 + '\n')
                f.write('Log reset:' + str(time.strftime(time.asctime())) + '\n')
                f.write('#' * 80 + '\n')
                f.close()
                logTimeNextReset = time.time() + int(iLogTime)

            # Check to see if iFindStuff is running for GeoFencing
            iFindStuffId = "com.corporatechameleon.iFindplugBeta"
            iFindStuffPlugin = indigo.server.getPlugin(iFindStuffId)
            if iFindStuffPlugin.isEnabled():
                gFindStuff = True

            # Now refresh API and devices
            nestAPI = setupAPI(nestTest)
            nestMap = nestMapping(nestSecure, nestFirst)

            if nestMap[0]:
                refreshNests(nestMap[1], nestAPI[0], nestAPI[1], nestFirst)

                nestFirst = False

                # Standard fields are held for the whole NEST Structure and these are managed at the
                # Plugin level.  With the exception of AWAY the others are managed on the NEST Device
                try:

                    # <-------- Multiple structures could exist therefore we need to store them with the Master
                    # <----- We could rename the device based on the nestHome name
                    # <------On creation we'll just use a random string until this finally gets called...

                    nestStructureKey = nestMap[2].keys()[0]
                    for vOther in range(len(nestAPI[2])):
                        nestCurrentValue = self.pluginPrefs[nestAPI[3][vOther]]
                        try:
                            self.pluginPrefs[nestAPI[3][vOther]] = nestMap[2][nestStructureKey][nestAPI[2][vOther]]
                        except KeyError:
                            continue


                except AttributeError:
                    # Structure is empty - probably failed in getting data
                    # Probable error because of an API failure

                    if nestDebug:
                        indigo.server.log(
                            u'Failed to access Structures data online (Structures) - try again in 60 seconds')
                    pass

                # Update the Master device with new details

                # <------------- We could have multiple master devices so we need to cycle here...

                nestMasterFound = False
                for dev in indigo.devices.iter('self.nestHomeMaster'):
                    nestMasterFound = True

                    # Update the fields on the device
                    try:
                        nestStructureKey = nestMap[2].keys()[0]
                        self.pluginPrefs['structure_key'] = nestStructureKey
                        for vOther in range(len(nestAPI[2])):
                            try:
                                nestCurrentValue = dev.states[nestAPI[3][vOther]]
                                nestNewValue = nestMap[2][nestStructureKey][nestAPI[2][vOther]]

                                if type(nestCurrentValue) == unicode or type(nestCurrentValue) == str:
                                    if nestAPI[3][vOther] == 'nestAway':
                                        nestCurrentValue = nestCurrentValue.capitalize()
                                        nestNewValue = nestNewValue.capitalize()

                                dev.updateStateOnServer(nestAPI[3][vOther], value=nestNewValue)

                                if not nestCurrentValue == nestNewValue:
                                    # Value has changed so advise in log
                                    if nestAPI[3][vOther] == 'nestAway':
                                        nestReport = 'Away'
                                    else:
                                        nestReport = nestAPI[3][vOther]

                                    if nestShowC:
                                        indigo.server.log(u"NEST " + nestReport + " has changed to "
                                                          + nestMap[2][nestStructureKey][nestAPI[2][vOther]])

                            except KeyError:
                                continue

                        if not nestMasterFound:
                            # No Master so we'll wait for the next refresh
                            pass

                    except AttributeError:
                        # Probable error because of an API failure
                        if nestDebug:
                            indigo.server.log(
                                u'Failed to access Structures data online (Master) - try again in 60 seconds')
                        pass

                # Finally update from iFindStuff if its running

                if gFindStuff:
                    # We are so refresh the thermo and protect devices from iFindStuff
                    iFindStuffId = "com.corporatechameleon.iFindplugBeta"
                    iFindStuffPlugin = indigo.server.getPlugin(iFindStuffId)
                    if iFindStuffPlugin.isEnabled():
                        # Thermostats first
                        for dev in indigo.devices.iter('self.nestThermostat'):
                            geoAccount = dev.states['geoAssignId']

                            if len(geoAccount) == 0:
                                # Not linked
                                continue

                            geoFence = indigo.devices[int(geoAccount)]

                            if 'geoActive' in geoFence.globalProps['com.corporatechameleon.iFindplugBeta']:
                                geoActive = geoFence.globalProps['com.corporatechameleon.iFindplugBeta']['geoActive']

                            if 'geoNEST' in geoFence.globalProps['com.corporatechameleon.iFindplugBeta']:
                                geoNEST = geoFence.globalProps['com.corporatechameleon.iFindplugBeta']['geoNEST']

                            if geoActive and geoNEST:
                                # Active and a NEST Geo
                                dev.updateStateOnServer('geoAssignId', str(geoFence.id))
                                dev.updateStateOnServer('geoAssignName', geoFence.name)
                                dev.updateStateOnServer('geoNESTRange', int(geoFence.states['devicesInNestRange']))
                                dev.updateStateOnServer('geoNearRange', int(geoFence.states['devicesNear']))
                            else:
                                # Not active or no longer a NEST geo
                                dev.updateStateOnServer('geoAssignId', '')
                                dev.updateStateOnServer('geoAssignName', '')
                                dev.updateStateOnServer('geoNESTRange', 0)
                                dev.updateStateOnServer('geoNearRange', 0)
                                indigo.server.log(
                                    dev.name + ' NEST Geo ' + geoFence.name + ' either Inactive or no longer a NEST Geo',
                                    isError=True)

                        # Now Protects
                        for dev in indigo.devices.iter('self.nestProtect'):
                            geoAccount = dev.states['proAssignId']

                            if len(geoAccount) == 0:
                                # Not linked
                                continue

                            geoFence = indigo.devices[int(geoAccount)]
                            geoProps = geoFence.pluginProps

                            if 'geoActive' in geoFence.globalProps['com.corporatechameleon.iFindplugBeta']:
                                geoActive = geoFence.globalProps['com.corporatechameleon.iFindplugBeta']['geoActive']

                            if 'geoNEST' in geoFence.globalProps['com.corporatechameleon.iFindplugBeta']:
                                geoNEST = geoFence.globalProps['com.corporatechameleon.iFindplugBeta']['geoNEST']

                            if geoActive and geoNEST:
                                # Active and a NEST Geo
                                dev.updateStateOnServer('proAssignId', str(geoFence.id))
                                dev.updateStateOnServer('proAssignName', geoFence.name)
                                dev.updateStateOnServer('proNESTRange', int(geoFence.states['devicesInNestRange']))
                                dev.updateStateOnServer('proNearRange', int(geoFence.states['devicesNear']))
                            else:
                                # Not active or no longer a NEST geo
                                dev.updateStateOnServer('proAssignId', '')
                                dev.updateStateOnServer('proAssignName', '')
                                dev.updateStateOnServer('proNESTRange', 0)
                                dev.updateStateOnServer('proNearRange', 0)
                                indigo.server.log(
                                    dev.name + ' NEST Geo ' + geoFence.name + ' either Inactive or no longer a NEST Geo',
                                    isError=True)

            else:
                if nestDebug:
                    indigo.server.log(u'Failed to access API - MAIN THREAD')

            self.sleep(nestTimer)

    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        return (True, valuesDict)

    ########################################
    def deviceStartComm(self, dev):
        dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used

    def deviceStopComm(self, dev):
        # Called when communication with the hardware should be shutdown.
        pass

    def deviceUpdated(self, originalDev, newDev):
        global db

        # Called when communication with the hardware should be shutdown.
        # Processes changes to devices for tracking purposes in this case

        if (originalDev.deviceTypeId != 'nestThermostat' and originalDev.deviceTypeId != 'nestHomeMaster') \
                or originalDev.pluginId != 'com.corporatechameleon.nestplugBeta':
            # Only tracking thermostats and accounts for away/home at this point so just return
            return

        # Process the change
        self.nestDataManagement = self.pluginPrefs.get('nestData', 'false')

        if self.nestDataManagement != 'false':
            self.dataChange(originalDev, newDev)

        # Done so return
        return

    ########################################
    #  Data Tracking & Management modules
    ######################
    # Code designed to manage archive data from NEST Changes for later analysis

    def dataChange(self, oldDev, newDev):
        global db

        # Identifies changes to the NEST device and tracks changes
        # Note that there are multiple devices allowed so these must be identified
        # In the data log
        # Users can produce a text report or create a CSV file for Excel
        # this functionality is covered in other modules

        # Is this a Home/Away account device?
        if oldDev.deviceTypeId == 'nestHomeMaster':
            # We want to check for the Home/Away change
            if oldDev.states['nestAway'] == newDev.states['nestAway']:
                # Not a change in status
                return
            else:
                # Change in mode
                nestMessage = 'Home/Away change'
                if newDev.states['nestAway'].upper() == 'AWAY':
                    nestEvent = 'NEST changed from ' + oldDev.states['nestAway'].capitalize() + ' to Away'
                elif newDev.states['nestAway'].upper() == 'HOME':
                    nestEvent = 'NEST changed from ' + oldDev.states['nestAway'].capitalize() + ' to Home'
                else:
                    nestEvent = 'NEST changed from ' + oldDev.states['nestAway'].capitalize() + ' to Off'

                nestValue = str(newDev.states['nestAway']).capitalize()

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                return

        # Check for changes and classify - iterate through the fields automatically
        # First a list of the key fields we're interested in
        nestKeyFields = ["fan_timer_active",
                         "has_leaf",
                         "hvac_mode",
                         "target_temperature_f",
                         "target_temperature_c",
                         "target_temperature_high_f",
                         "target_temperature_low_f",
                         "target_temperature_high_c",
                         "target_temperature_low_c",
                         "ambient_temperature_f",
                         "ambient_temperature_c",
                         "away_temperature_high_f",
                         "away_temperature_high_c",
                         "away_temperature_low_f",
                         "away_temperature_low_c",
                         "humidity",
                         "hvac_state"
                         ]

        # Get the current scale F or C
        nestScale = newDev.states['temperature_scale'].lower()

        # Dual system?
        nestDual = newDev.states['can_cool'] and newDev.states['can_heat']

        # Has fan?
        nestFan = newDev.states['has_fan']

        for nestField in oldDev.states:
            if nestKeyFields.count(nestField) == 0:
                # Not a key field so ignore
                continue

            if nestField.find('temperature') != -1:
                # This is a temperature field
                # Compare the fields
                if float(oldDev.states[nestField]) == float(newDev.states[nestField]):
                    # No change in field so check the next one
                    continue

                elif nestField.lower().find(nestScale) == -1:
                    # This is a temperature field but not in the scale that we're using on this device
                    # so ignore
                    continue

                elif nestField == 'ambient_temperature_' + nestScale:

                    # Change in ambient temperature
                    nestMessage = 'Ambient change'
                    nestTempChange = float(oldDev.states[nestField]) - float(newDev.states[nestField])
                    if nestTempChange < 0:
                        nestEvent = 'Increase in ambient of ' + str(abs(nestTempChange)) + ' ' + nestScale.upper()
                    else:
                        nestEvent = 'Decrease in ambient of ' + str(abs(nestTempChange)) + ' ' + nestScale.upper()

                    nestValue = str(newDev.states[nestField])

                    # Write changes to database
                    self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                    continue

                elif nestDual:
                    if nestField.find('high') == -1 and nestField.find('low') == -1:
                        # This is not a Dual system temperature field so ignore
                        continue

                    if nestField.find('away') != -1:
                        nestTemp1Field = 'Away'
                    else:
                        nestTemp1Field = 'Target'

                    if nestField.find('high') != -1:
                        nestTemp2Field = 'coolpoint'
                    else:
                        nestTemp2Field = 'heatpoint'

                    nestTypeMessage = nestTemp1Field + ' ' + nestTemp2Field

                    # Change in the setpoint
                    nestMessage = nestTypeMessage + ' change'
                    nestTempChange = float(oldDev.states[nestField]) - float(newDev.states[nestField])
                    if nestTempChange < 0:
                        nestEvent = 'Increase in ' + nestTypeMessage + ' of ' + str(
                            abs(nestTempChange)) + ' ' + nestScale.upper()
                    else:
                        nestEvent = 'Decrease in ' + nestTypeMessage + ' of ' + str(
                            abs(nestTempChange)) + ' ' + nestScale.upper()

                    nestValue = str(newDev.states[nestField])

                    # Write changes to database
                    self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                    continue

                elif not nestDual:
                    if nestField.find('high') != -1 or nestField.find('low') != -1:
                        # Dual system field so ignore
                        continue

                    # Single system so there are only two fields to change
                    nestTemp1Field = 'Target'

                    nestTypeMessage = nestTemp1Field + ' setpoint'

                    # Change in the setpoint
                    nestMessage = nestTypeMessage + ' change'
                    nestTempChange = float(oldDev.states[nestField]) - float(newDev.states[nestField])
                    if nestTempChange < 0:
                        nestEvent = 'Increase in ' + nestTypeMessage + ' of ' + str(
                            abs(nestTempChange)) + ' ' + nestScale.upper()
                    else:
                        nestEvent = 'Decrease in ' + nestTypeMessage + ' of ' + str(
                            abs(nestTempChange)) + ' ' + nestScale.upper()

                    nestValue = str(newDev.states[nestField])

                    # Write changes to database
                    self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                    continue

            elif nestField == 'hvac_mode':
                # Compare the fields
                if oldDev.states[nestField] == newDev.states[nestField]:
                    # No change in field so check the next one
                    continue

                # Change in the hvac mode heat, cool, heat-cool or off
                nestMessage = 'HVAC mode'
                nestEvent = 'HVAC mode changed from ' + oldDev.states['hvac_mode'] + ' to ' + newDev.states['hvac_mode']
                nestValue = newDev.states['hvac_mode'].capitalize()

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                continue

            elif nestField == 'hvac_state':
                # Compare the fields
                if oldDev.states[nestField] == newDev.states[nestField]:
                    # No change in field so check the next one
                    continue

                # Change in the hvac state heating, cooling or off
                nestMessage = 'HVAC state'
                nestEvent = 'HVAC state changed from ' + oldDev.states['hvac_state'] + ' to ' + newDev.states[
                    'hvac_state']
                nestValue = newDev.states['hvac_state'].capitalize()

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                continue

            elif nestField == 'has_leaf':
                # Compare the fields
                if oldDev.states[nestField] == newDev.states[nestField]:
                    # No change in field so check the next one
                    continue

                # Change in the leaf mode True or False
                nestMessage = 'Leaf mode'
                if newDev.states['has_leaf']:
                    nestTemp1Field = 'displayed'
                    nestTemp2Field = 'not displayed'
                else:
                    nestTemp1Field = 'not displayed'
                    nestTemp2Field = 'displayed'

                nestEvent = 'Leaf mode changed from ' + nestTemp2Field + ' to ' + nestTemp1Field
                nestValue = str(newDev.states['has_leaf'])

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                continue

            elif nestField == 'humidity':
                # Compare the fields
                if int(oldDev.states[nestField]) == int(newDev.states[nestField]):
                    # No change in field so check the next one
                    continue

                # Change in the humidity internal as a %
                nestMessage = 'Humidity change'
                nestTypeMessage = 'Humidity'
                nestHumChange = int(oldDev.states[nestField]) - int(newDev.states[nestField])
                if nestHumChange < 0:
                    nestEvent = 'Increase in ' + nestTypeMessage + ' of ' + str(abs(nestHumChange)) + str('%')
                else:
                    nestEvent = 'Decrease in ' + nestTypeMessage + ' of ' + str(abs(nestHumChange)) + str('%')

                nestValue = str(newDev.states[nestField])

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                continue

            elif nestField == 'fan_timer_active' and nestFan:
                # Compare the fields
                if oldDev.states[nestField] == newDev.states[nestField]:
                    # No change in field so check the next one
                    continue

                # Change in the fan on or off
                nestMessage = 'Fan'
                if newDev.states['fan_timer_active']:
                    nestTemp1Field = 'on'
                    nestTemp2Field = 'off'
                else:
                    nestTemp1Field = 'off'
                    nestTemp2Field = 'on'

                nestEvent = 'Fan mode changed from ' + nestTemp2Field + ' to ' + nestTemp1Field
                nestValue = str(newDev.states['fan_timer_active'])

                # Write changes to database
                self.nestFileWrite(oldDev, newDev, nestMessage, nestEvent, nestValue)
                continue

    def nestFileWrite(self, oldDev, newDev, nestMessage, nestEvent, nestValue):
        global db

        # This module opens the current database and adds the information to the file
        devName = newDev.name
        devIndigoId = newDev.id
        eventTimeStamp = time.localtime()
        eventReadTime = time.strftime('%a %d %b %Y %H:%M:%S', eventTimeStamp)
        eventTimeStamp = time.mktime(eventTimeStamp)

        # Write data to db as a string of values in a dictionary
        nestDataUpdate = {}
        nestDataUpdate['timestamp'] = eventTimeStamp
        nestDataUpdate['timeread'] = eventReadTime
        nestDataUpdate['devname'] = devName
        nestDataUpdate['devid'] = devIndigoId
        nestDataUpdate['nestMessage'] = nestMessage
        nestDataUpdate['nestEvent'] = nestEvent
        nestDataUpdate['nestValue'] = nestValue

        # Add data to database
        try:
            db.insert(nestDataUpdate)
        except:
            # Database didn't open properly probably due to error in the directory name in the preferences.  To
            # recover we will disable reporting and advise the user of the issue
            self.pluginPrefs['nestData'] = 'false'
            self.nestDataManagement = 'false'
            indigo.server.log(
                '** Warning - problems with historial data tracking probably due to the Text File Directory **',
                isError=True)
            indigo.server.log('** being incorrectly entered or blank **', isError=True)
            indigo.server.log('** If you want to use data tracking please correct in the configuration dialog and **',
                              isError=True)
            indigo.server.log('** recheck the Should NEST Home archive data? option **', isError=True)
            indigo.server.log('** Otherwise please ignore this message **', isError=True)

        # Next field check
        return

    def nestDataOut(self, valuesDict=None, dev=0, typeId=0, supress=False):
        global db

        # Allows the user to specify date range and type of data to be output
        # Data is extracted from the Data Management database

        # Is tracking on?
        if not self.nestDataManagement:
            # Not actually tracking so send an error to the log
            indigo.server.log('** Data Management Option not selected - check NEST Home Configuration **', isError=True)
            return

        # Set up error dictionary
        errorDict = indigo.Dict()

        # Get requirements from config
        allData = valuesDict['exportAllData']
        if not allData:
            exportStart = valuesDict['exportRangeStart']
            exportEnd = valuesDict['exportRangeEnd']

            # Check range data
            if exportStart == '00/00/00' or exportEnd == '00/00/00':

                # Times still blank so report error
                if exportStart == '00/00/00':
                    errorDict = indigo.Dict()
                    errorDict["exportRangeStart"] = "Invalid Start Date 00/00/00"
                    errorDict["showAlertText"] = "You enter a valid start date for the range or select all data"
                    return (False, valuesDict, errorDict)
                else:
                    errorDict = indigo.Dict()
                    errorDict["exportRangeEnd"] = "Invalid End Date 00/00/00"
                    errorDict["showAlertText"] = "You enter a valid end date for the range or select all data"
                    return (False, valuesDict, errorDict)

            # Now check that date is valid
            try:
                exportTimeStart = time.mktime(time.strptime(exportStart, '%d/%m/%y'))
            except:
                errorDict = indigo.Dict()
                errorDict["exportRangeStart"] = "The start date isn't valid - format is dd/mm/yy"
                errorDict["showAlertText"] = "The date format is day/month/year (dd/mm/yy) please re-enter"
                return (False, valuesDict, errorDict)

            try:
                exportTimeEnd = time.mktime(time.strptime(exportEnd, '%d/%m/%y'))
            except:
                errorDict = indigo.Dict()
                errorDict["exportRangeEnd"] = "The end date isn't valid - format is dd/mm/yy"
                errorDict["showAlertText"] = "The date format is day/month/year (dd/mm/yy) please re-enter"
                return (False, valuesDict, errorDict)

            # Is the start date less than or equal to the end date
            if exportTimeStart > exportTimeEnd:
                errorDict = indigo.Dict()
                errorDict["exportRangeEnd"] = "End date is less than Start date"
                errorDict["showAlertText"] = "The start date must be less than or equal to the end date"
                return (False, valuesDict, errorDict)

            # Get the rest of the options
            tempData = valuesDict['dataTemperature']
            humData = valuesDict['dataHumidity']
            hvacData = valuesDict['dataHVAC']
            setData = valuesDict['dataSetpoint']
            leafData = valuesDict['dataLeaf']
            awayData = valuesDict['dataAway']

        else:
            exportTimeStart = 0
            exportTimeEnd = time.mktime(time.localtime())
            exportStart = '00/00/00'
            exportEnd = '00/00/00'

            # Get all data of the options
            tempData = True
            humData = True
            hvacData = True
            setData = True
            leafData = True
            awayData = True

        if not tempData and not humData and not hvacData and not setData and not leafData and not awayData:
            # Nothing selected for the report
            errorDict = indigo.Dict()
            errorDict["dataTemperature"] = "Nothing selected for report - please check or cancel"
            errorDict["showAlertText"] = "You haven't selected any data for NEST Home to export"
            return (False, valuesDict, errorDict)

        # Add a day onto the end date so that we get a maximum value
        # Data we want will have a timestamp greater than exportTimeStart and less than exportTimeEnd + one day
        exportTimeEnd = exportTimeEnd + 24 * 60 * 60  # Seconds in a day

        # Let's get the Home/Away information out from the account master first
        for master in indigo.devices.iter('self.nestHomeMaster'):

            if awayData:
                # Extract the temp data
                exportData = db.search((where('devid') == master.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       (where('nestMessage') == 'Home/Away change'))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'Home Away Status', master, supress)

        # Ok lets extract the data from the database for each NestThermostat
        for thermo in indigo.devices.iter('self.nestThermostat'):

            if tempData:
                # Extract the temp data
                exportData = db.search((where('devid') == thermo.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       (where('nestMessage') == 'Ambient change'))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'Ambient Temperature', thermo, supress)

            if humData:
                # Extract the humidity data
                exportData = db.search((where('devid') == thermo.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       (where('nestMessage') == 'Humidity change'))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'Humidity', thermo, supress)

            if setData:
                # Extract the setpoint data
                nestQuery = Query()
                exportData = db.search((where('devid') == thermo.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       ((nestQuery.nestMessage.matches('Away*') | (
                                       nestQuery.nestMessage.matches('Target*')))))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'Setpoints', thermo, supress)

            if hvacData:
                # Extract the hvac data
                nestQuery = Query()
                exportData = db.search((where('devid') == thermo.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       (nestQuery.nestMessage.matches('HVAC*')))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'HVAC Data', thermo, supress)

            if leafData:
                # Extract the hvac data
                nestQuery = Query()
                exportData = db.search((where('devid') == thermo.id) &
                                       (where('timestamp') >= exportTimeStart) &
                                       (where('timestamp') < exportTimeEnd) &
                                       (nestQuery.nestMessage.matches('Leaf*')))

                # Convert the data to list in right order
                self.convertDicttoList(exportData, exportStart, exportEnd, 'Leaf changes', thermo, supress)

        return True

    def convertDicttoList(self, exportData=None, exportStart='00/00/00', exportEnd='00/00/00', filePostScript='', dev=0,
                          supress=False):
        # Converts a dictionary to a list suitable for export as a CSV or text reporting
        if len(exportData) == 0:
            # No data to convert
            indigo.server.log('** No ' + filePostScript + ' data to report for Device ' + dev.name + '**')
            return

            # Collect date for file created

        startText = exportStart.replace('/', '-')
        endText = exportEnd.replace('/', '-')
        if startText == '00-00-00':
            iFileName = 'NEST Report (ALL DATA)'
            iFileName = self.nestStorage + '/' + iFileName.upper()
        else:
            iFileName = 'NEST Report (' + startText + ' : ' + endText + ')'
            iFileName = self.nestStorage + '/' + iFileName.upper()

        # Heading Row for the file
        headingRow = ['Time stamp', 'Time Text', 'Indigo Id', 'Device Name', 'Event Type', 'Event Description',
                      'NEST Home Value']

        # Order of the data required
        myKeys = ['timestamp', 'timeread', 'devid', 'devname', 'nestMessage', 'nestEvent', 'nestValue']
        exportKeys = exportData[0].keys()

        # Now extract the data into a list we can use
        myDataList = []
        for line in range(len(exportData)):
            # Process each line in turn
            # Get a list of values
            myValues = exportData[line].values()

            # Now order them according to what we want to export
            myTempValues = []
            exportKeys = exportData[line].keys()
            for k in range(len(myKeys)):
                keyPosition = exportKeys.index(myKeys[k])
                myTempValues.append(myValues[keyPosition])

            myDataList.append(myTempValues)

        # Now export headings
        tempFileName = iFileName + ' ' + filePostScript + '.csv'
        myCSVFile = open(tempFileName, 'w')
        headingRowLen = len(headingRow) - 1
        currentElement = 0
        for element in headingRow:
            if currentElement != headingRowLen:
                myCSVFile.write(str(element) + ',')

            else:
                myCSVFile.write(str(element))

            currentElement = currentElement + 1

        # Add a newline on the end
        myCSVFile.write('\n')

        # Now the actual data
        for line in range(len(myDataList)):
            CSVData = myDataList[line]
            dataRowLen = len(CSVData) - 1
            currentElement = 0
            for element in CSVData:
                if currentElement != dataRowLen:
                    myCSVFile.write(str(element) + ',')
                else:
                    myCSVFile.write(str(element))

                currentElement = currentElement + 1

            myCSVFile.write('\n')

        # Close the CS File
        myCSVFile.close()
        indigo.server.log('** Exported ' + str(len(exportData)) + ' records to ' + tempFileName + ' **')

        return

    def reportDataOut(self, valuesDict=None, dev=0, typeId=0):
        global db

        # Allows the user to specify date range and type of data to be output
        # Data is extracted from the Data Management database

        # Is tracking on?
        if not self.nestDataManagement:
            # Not actually tracking so send an error to the log
            indigo.server.log('** Data Management Option not selected - check NEST Home Configuration **', isError=True)
            return

        # Set up error dictionary
        errorDict = indigo.Dict()

        # Setup export Dict
        exportDict = {}

        # Get requirements from config
        allData = valuesDict['reportAllData']
        fileReport = valuesDict['reportFile']
        exportDict['exportAllData'] = allData

        if not allData:
            reportStart = valuesDict['reportRangeStart']
            reportEnd = valuesDict['reportRangeEnd']
            exportDict['exportRangeStart'] = reportStart
            exportDict['exportRangeEnd'] = reportEnd

            # Check range data
            if reportStart == '00/00/00' or reportEnd == '00/00/00':

                # Times still blank so report error
                if reportStart == '00/00/00':
                    errorDict = indigo.Dict()
                    errorDict["reportRangeStart"] = "Invalid Start Date 00/00/00"
                    errorDict["showAlertText"] = "You enter a valid start date for the range or select all data"
                    return (False, valuesDict, errorDict)
                else:
                    errorDict = indigo.Dict()
                    errorDict["reportRangeEnd"] = "Invalid End Date 00/00/00"
                    errorDict["showAlertText"] = "You enter a valid end date for the range or select all data"
                    return (False, valuesDict, errorDict)

            # Now check that date is valid
            try:
                reportTimeStart = time.mktime(time.strptime(reportStart, '%d/%m/%y'))
            except:
                errorDict = indigo.Dict()
                errorDict["reportRangeStart"] = "The start date isn't valid - format is dd/mm/yy"
                errorDict["showAlertText"] = "The date format is day/month/year (dd/mm/yy) please re-enter"
                return (False, valuesDict, errorDict)

            try:
                reportTimeEnd = time.mktime(time.strptime(reportEnd, '%d/%m/%y'))
            except:
                errorDict = indigo.Dict()
                errorDict["reportRangeEnd"] = "The end date isn't valid - format is dd/mm/yy"
                errorDict["showAlertText"] = "The date format is day/month/year (dd/mm/yy) please re-enter"
                return (False, valuesDict, errorDict)

            # Is the start date less than or equal to the end date
            if reportTimeStart > reportTimeEnd:
                errorDict = indigo.Dict()
                errorDict["reportRangeEnd"] = "End date is less than Start date"
                errorDict["showAlertText"] = "The start date must be less than or equal to the end date"
                return (False, valuesDict, errorDict)

            # Get the rest of the options
            tempData = valuesDict['reportTemperature']
            humData = valuesDict['reportHumidity']
            hvacData = valuesDict['reportHVAC']
            setData = valuesDict['reportSetpoint']
            leafData = valuesDict['reportLeaf']
            awayData = valuesDict['reportAway']
            exportDict['dataTemperature'] = tempData
            exportDict['dataHumidity'] = humData
            exportDict['dataHVAC'] = hvacData
            exportDict['dataSetpoint'] = setData
            exportDict['dataLeaf'] = leafData
            exportDict['dataAway'] = awayData

        else:
            reportTimeStart = 0
            reportTimeEnd = time.mktime(time.localtime())
            reportStart = '00/00/00'
            reportEnd = '00/00/00'

            # Get all data of the options
            tempData = True
            humData = True
            hvacData = True
            setData = True
            leafData = True
            awayData = True
            exportDict['dataTemperature'] = tempData
            exportDict['dataHumidity'] = humData
            exportDict['dataHVAC'] = hvacData
            exportDict['dataSetpoint'] = setData
            exportDict['dataLeaf'] = leafData
            exportDict['dataAway'] = awayData

        if not tempData and not humData and not hvacData and not setData and not leafData and not awayData:
            # Nothing selected for the report
            errorDict = indigo.Dict()
            errorDict["reportTemperature"] = "Nothing selected for report - please check or cancel"
            errorDict["showAlertText"] = "You haven't selected any data for NEST Home to report"
            return (False, valuesDict, errorDict)

        # Add a day onto the end date so that we get a maximum value
        # Data we want will have a timestamp greater than reportTimeStart and less than reportTimeEnd + one day
        reportTimeEnd = reportTimeEnd + 24 * 60 * 60  # Seconds in a day


        # Export the data to CSV files
        self.nestDataOut(exportDict, 0, 0, True)

        # Let's get report on the Home/Away information out from the account master first
        for master in indigo.devices.iter('self.nestHomeMaster'):

            if awayData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.homeAwayFile(reportRange, 'Home Away Status', master)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.homeAway(reportRange, 'Home Away Status', master)

        # Ok lets extract the data from the database for each NestThermostat
        for thermo in indigo.devices.iter('self.nestThermostat'):

            if tempData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.AmbientReportFile(reportRange, 'Ambient Temperature', thermo)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.AmbientReport(reportRange, 'Ambient Temperature', thermo)

            if humData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.HumidityFile(reportRange, 'Humidity', thermo)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.Humidity(reportRange, 'Humidity', thermo)

            if setData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.setPointFile(reportRange, 'Setpoints', thermo)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.setPoint(reportRange, 'Setpoints', thermo)

            if hvacData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.HVACFile(reportRange, 'HVAC Data', thermo)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.HVAC(reportRange, 'HVAC Data', thermo)

            if leafData:

                # Report on data selected
                if fileReport:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.LeafFile(reportRange, 'Leaf changes', thermo)
                else:
                    reportRange = reportStart + ' : ' + reportEnd
                    self.Leaf(reportRange, 'Leaf changes', thermo)
        return True

    def AmbientReport(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Ambient Temperature.csv'
            f = open(myFile, 'r')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()
        highTemp = 0.0
        lowTemp = 100.0
        averTemp = 0.0
        entries = float(len(myList) - 1)
        totalTemp = 0.0

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home Ambient Temperature Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(5)[:5]
        indigo.server.log(Head1 + Head2 + Head3)
        print lineHeading2

        for dataLine in range(len(myList) - 1):
            # if dataLine == 0:
            #    # This is the heading line so ignore it
            #    continue

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Analysis
            if float(Data3) > highTemp:
                highTemp = float(Data3)

            if float(Data3) < lowTemp:
                lowTemp = float(Data3)

            totalTemp = totalTemp + float(Data3)

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading2)
        indigo.server.log('** Analysis **\n')
        indigo.server.log(('Highest Temperature: ').ljust(25)[:25] + str(round(highTemp, 1)))
        indigo.server.log(('Lowest Temperature: ').ljust(25)[:25] + str(round(lowTemp, 1)))
        averTemp = round(totalTemp / entries, 1)
        indigo.server.log(('Average Temperature: ').ljust(25)[:25] + str(round(averTemp, 2)))
        indigo.server.log(lineHeading + '\n')

    def Humidity(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Humidity.csv'
            f = open(myFile, 'r')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home Indoor Humidity Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(5)[:5]
        indigo.server.log(Head1 + Head2 + Head3)
        indigo.server.log(lineHeading2)

        for dataLine in range(len(myList) - 1):
            # if dataLine == 0:
            #    # This is the heading line so ignore it
            #    continue

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading + '\n')

    def Leaf(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Leaf changes.csv'
            f = open(myFile, 'r')
        except IOError:
            return
        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home Leaf Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(50)[:50]
        Head3 = 'Value'.ljust(5)[:5]
        indigo.server.log(Head1 + Head2 + Head3)
        indigo.server.log(lineHeading2)
        numberLeaf = 0

        for dataLine in range(len(myList) - 1):
            if myList[dataLine][6] == 'True':
                numberLeaf = numberLeaf + 1

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(50)[:50]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading2)
        indigo.server.log('** Analysis **\n')
        indigo.server.log('Total leaves gained: ' + str(numberLeaf))
        indigo.server.log(lineHeading + '\n')

    def homeAway(self, reportRange='00/00/00 : 00/00/00', filePost='', master=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Home Away Status.csv'
            f = open(myFile, 'r')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()

        # Print Headings
        myDevice = master.name
        myDeviceId = str(master.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        totalHome = 0.0
        totalAway = 0.0
        totalOff = 0.0
        timesAway = 0
        timesHome = 0
        timesOff = 0
        timeDataLast = -1
        statusLast = 'Off'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home Home/Away Status Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        indigo.server.log(Head1 + Head2 + Head3)
        indigo.server.log(lineHeading2)

        for dataLine in range(len(myList) - 1):

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            if timeDataLast == -1:
                # First line
                timeDataNow = float(myList[dataLine][0])
                timeDataLast = float(myList[dataLine][0])
                timeStatus = Data3.capitalize()

            else:
                timeDataLast = timeDataNow
                timeDataNow = float(myList[dataLine][0])

                # Calculate time on last mode
                timeDiff = timeDataNow - timeDataLast
                timeHours = timeDiff / 3600.
                if timeStatus.upper().rstrip() == 'AWAY':
                    totalAway = totalAway + timeHours
                elif timeStatus.upper().rstrip() == 'HOME':
                    totalHome = totalHome + timeHours
                else:
                    totalOff = totalOff + timeHours

            timeStatus = Data3.capitalize()

            if Data3.upper().rstrip() == 'AWAY':
                timesAway = timesAway + 1
            elif Data3.upper().rstrip() == 'HOME':
                timesHome = timesHome + 1
            else:
                timesOff = timesOff + 1

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading2)
        indigo.server.log('** Analysis **\n')
        indigo.server.log(
            ('Total Times Away: '.ljust(25)[:25] + str(timesAway)).ljust(30)[:30] + '  Total Hours Heating: '.ljust(25)[
                                                                                    :25] + str(round(totalAway, 1)))
        indigo.server.log(
            ('Total Times Home: '.ljust(25)[:25] + str(timesHome)).ljust(30)[:30] + '  Total Hours Cooling: '.ljust(25)[
                                                                                    :25] + str(round(totalHome, 1)))
        indigo.server.log(
            ('Total Times Off: '.ljust(25)[:25] + str(timesOff)).ljust(30)[:30] + '  Total Hours Off: '.ljust(25)[
                                                                                  :25] + str(round(totalOff, 1)))
        indigo.server.log(lineHeading + '\n')

    def HVAC(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') HVAC Data.csv'
            f = open(myFile, 'r')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = thermo.id
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        totalHeating = 0.0
        totalCooling = 0.0
        totalOff = 0.0
        timesHeat = 0
        timesCool = 0
        timesOff = 0
        timeDataLast = -1
        statusLast = 'Off'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home HVAC Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        indigo.server.log(Head1 + Head2 + Head3)
        indigo.server.log(lineHeading2)

        for dataLine in range(len(myList) - 1):

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            if timeDataLast == -1:
                # First line
                timeDataNow = float(myList[dataLine][0])
                timeDataLast = float(myList[dataLine][0])
                timeStatus = Data3.capitalize()

            else:
                timeDataLast = timeDataNow
                timeDataNow = float(myList[dataLine][0])

                # Calculate time on last mode
                timeDiff = timeDataNow - timeDataLast
                timeHours = timeDiff / 3600.
                if timeStatus.upper().rstrip() == 'HEATING':
                    totalHeating = totalHeating + timeHours
                elif timeStatus.upper().rstrip() == 'COOLING':
                    totalCooling = totalCooling + timeHours
                else:
                    totalOff = totalOff + timeHours

            timeStatus = Data3.capitalize()

            if Data3.upper().rstrip() == 'HEATING':
                timesHeat = timesHeat + 1
            elif Data3.upper().rstrip == 'COOLING':
                timesCool = timesCool + 1
            else:
                timesOff = timesOff + 1

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading2)
        indigo.server.log('** Analysis **\n')
        indigo.server.log(
            ('Total Times Heating: '.ljust(25)[:25] + str(timesHeat)).ljust(30)[:30] + '  Total Hours Heating: '.ljust(
                25)[:25] + str(round(totalHeating, 1)))
        indigo.server.log(
            ('Total Times Cooling: '.ljust(25)[:25] + str(timesCool)).ljust(30)[:30] + '  Total Hours Cooling: '.ljust(
                25)[:25] + str(round(totalCooling, 1)))
        indigo.server.log(
            ('Total Times Off: '.ljust(25)[:25] + str(timesOff)).ljust(30)[:30] + '  Total Hours Off: '.ljust(25)[
                                                                                  :25] + str(round(totalOff, 1)))
        indigo.server.log(lineHeading + '\n')

    def setPoint(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # All data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Setpoints.csv'
            f = open(myFile, 'r')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = thermo.id
        noEntry = str(len(myList) - 1) + ' Entries found for report'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        indigo.server.log(lineHeading)
        indigo.server.log('NEST Home Setpoints Report  ')
        indigo.server.log('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n')
        indigo.server.log('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId))
        indigo.server.log('Statistics: ' + noEntry)
        indigo.server.log(lineHeading)

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        indigo.server.log(Head1 + Head2 + Head3)
        indigo.server.log(lineHeading2)

        for dataLine in range(len(myList) - 1):
            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            # Print it
            indigo.server.log(Data1 + Data2 + Data3)

        indigo.server.log(lineHeading + '\n')

    def AmbientReportFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Ambient Temperature.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Ambient Temperature.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')

        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        highTemp = 0.0
        lowTemp = 100.0
        averTemp = 0.0
        entries = float(len(myList) - 1)
        totalTemp = 0.0
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading + '\n')
        f2.write('NEST Home Ambient Temperature Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(5)[:5]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')

        for dataLine in range(len(myList) - 1):
            # if dataLine == 0:
            #    # This is the heading line so ignore it
            #    continue

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Analysis
            if float(Data3) > highTemp:
                highTemp = float(Data3)

            if float(Data3) < lowTemp:
                lowTemp = float(Data3)

            totalTemp = totalTemp + float(Data3)

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading2 + '\n')
        f2.write('** Analysis **\n' + '\n')
        f2.write(('Highest Temperature: ').ljust(25)[:25] + str(round(highTemp, 1)) + '\n')
        f2.write(('Lowest Temperature: ').ljust(25)[:25] + str(round(lowTemp, 1)) + '\n')
        averTemp = round(totalTemp / entries, 1)
        f2.write(('Average Temperature: ').ljust(25)[:25] + str(round(averTemp, 2)) + '\n')
        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** Ambient Data Report Completed **')

    def HumidityFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Humidity.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Humidity.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')
        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading + '\n')
        f2.write('NEST Home Indoor Humidity Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(5)[:5]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')

        for dataLine in range(len(myList) - 1):
            # if dataLine == 0:
            #    # This is the heading line so ignore it
            #    continue

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** Humidity Data Report Completed **')

    def LeafFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Leaf changes.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Leaf changes.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')

        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading)
        f2.write('NEST Home Leaf Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(50)[:50]
        Head3 = 'Value'.ljust(5)[:5]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')
        numberLeaf = 0

        for dataLine in range(len(myList) - 1):
            if myList[dataLine][6] == 'True':
                numberLeaf = numberLeaf + 1

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][5].ljust(50)[:50]
            Data3 = myList[dataLine][6].ljust(5)[:5]

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading2 + '\n')
        f2.write('** Analysis **\n' + '\n')
        f2.write('Total leaves gained: ' + str(numberLeaf) + '\n')
        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** Leaf Data Report Completed **')

    def homeAwayFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):
        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Home Away Status.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Home Away Status.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')

        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        totalHome = 0.0
        totalAway = 0.0
        totalOff = 0.0
        timesAway = 0
        timesHome = 0
        timesOff = 0
        timeDataLast = -1
        statusLast = 'Off'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading + '\n')
        f2.write('NEST Home Home/Away Status Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')

        for dataLine in range(len(myList) - 1):

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            if timeDataLast == -1:
                # First line
                timeDataNow = float(myList[dataLine][0])
                timeDataLast = float(myList[dataLine][0])
                timeStatus = Data3.capitalize()

            else:
                timeDataLast = timeDataNow
                timeDataNow = float(myList[dataLine][0])

                # Calculate time on last mode
                timeDiff = timeDataNow - timeDataLast
                timeHours = timeDiff / 3600.
                if timeStatus.upper().rstrip() == 'AWAY':
                    totalAway = totalAway + timeHours
                elif timeStatus.upper().rstrip() == 'HOME':
                    totalHome = totalHome + timeHours
                else:
                    totalOff = totalOff + timeHours

            timeStatus = Data3.capitalize()

            if Data3.upper().rstrip() == 'AWAY':
                timesAway = timesAway + 1
            elif Data3.upper().rstrip() == 'HOME':
                timesHome = timesHome + 1
            else:
                timesOff = timesOff + 1

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading2 + '\n')
        f2.write('** Analysis **\n')
        f2.write(
            ('Total Times Away: '.ljust(25)[:25] + str(timesAway)).ljust(30)[:30] + '  Total Hours Heating: '.ljust(25)[
                                                                                    :25] + str(
                round(totalAway, 1)) + '\n')
        f2.write(
            ('Total Times Home: '.ljust(25)[:25] + str(timesHome)).ljust(30)[:30] + '  Total Hours Cooling: '.ljust(25)[
                                                                                    :25] + str(
                round(totalHome, 1)) + '\n')
        f2.write(('Total Times Off: '.ljust(25)[:25] + str(timesOff)).ljust(30)[:30] + '  Total Hours Off: '.ljust(25)[
                                                                                       :25] + str(
            round(totalOff, 1)) + '\n')
        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** Home and Away Status Report Completed **')

    def HVACFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') HVAC Data.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') HVAC Data.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')

        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = str(thermo.id)
        noEntry = str(len(myList) - 1) + ' Entries found for report'
        totalHeating = 0.0
        totalCooling = 0.0
        totalOff = 0.0
        timesHeat = 0
        timesCool = 0
        timesOff = 0
        timeDataLast = -1
        statusLast = 'Off'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading)
        f2.write('NEST Home HVAC Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')

        for dataLine in range(len(myList) - 1):

            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            if timeDataLast == -1:
                # First line
                timeDataNow = float(myList[dataLine][0])
                timeDataLast = float(myList[dataLine][0])
                timeStatus = Data3.capitalize()

            else:
                timeDataLast = timeDataNow
                timeDataNow = float(myList[dataLine][0])

                # Calculate time on last mode
                timeDiff = timeDataNow - timeDataLast
                timeHours = timeDiff / 3600.
                if timeStatus.upper().rstrip() == 'HEATING':
                    totalHeating = totalHeating + timeHours
                elif timeStatus.upper().rstrip() == 'COOLING':
                    totalCooling = totalCooling + timeHours
                else:
                    totalOff = totalOff + timeHours

            timeStatus = Data3.capitalize()

            if Data3.upper().rstrip() == 'HEATING':
                timesHeat = timesHeat + 1
            elif Data3.upper().rstrip == 'COOLING':
                timesCool = timesCool + 1
            else:
                timesOff = timesOff + 1

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading2 + '\n')
        f2.write('** Analysis **\n' + '\n')
        f2.write(
            ('Total Times Heating: '.ljust(25)[:25] + str(timesHeat)).ljust(30)[:30] + '  Total Hours Heating: '.ljust(
                25)[:25] + str(round(totalHeating, 1)) + '\n')
        f2.write(
            ('Total Times Cooling: '.ljust(25)[:25] + str(timesCool)).ljust(30)[:30] + '  Total Hours Cooling: '.ljust(
                25)[:25] + str(round(totalCooling, 1)) + '\n')
        f2.write(('Total Times Off: '.ljust(25)[:25] + str(timesOff)).ljust(30)[:30] + '  Total Hours Off: '.ljust(25)[
                                                                                       :25] + str(
            round(totalOff, 1)) + '\n')
        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** HVAC Operation Report Completed **')

    def setPointFile(self, reportRange='00/00/00 : 00/00/00', filePost='', thermo=0):

        # Get CSV data in a list format
        reportRange = reportRange.replace('/', '-')
        if reportRange == '00-00-00 : 00-00-00':
            # This is an all data report
            reportRange = 'ALL DATA'
        try:
            myFile = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Setpoints.csv'
            myFile2 = '/Users/Michael/NESTMap/NEST REPORT (' + reportRange + ') Setpoints.txt'
            f1 = open(myFile, 'r')
            f2 = open(myFile2, 'w')

        except IOError:
            return

        myList = []
        for line in myFile:
            CSVData = f1.readline().replace('\n', '')
            myData = CSVData.split(',')
            if len(CSVData) != 0:
                myList.append(myData)

        # Sort the list
        myList.sort()
        f1.close()

        # Print Headings
        myDevice = thermo.name
        myDeviceId = thermo.id
        noEntry = str(len(myList) - 1) + ' Entries found for report'

        lineHeading = '=' * 90
        lineHeading2 = '-' * 90
        f2.write(lineHeading + '\n')
        f2.write('NEST Home Setpoints Report  ' + '\n')
        f2.write('Date Range: ' + myFile[myFile.find('(') + 1:myFile.find(')')].replace(' ', '') + '\n' + '\n')
        f2.write('Device Name: ' + myDevice + '  Indigo id: ' + str(myDeviceId) + '\n')
        f2.write('Statistics: ' + noEntry + '\n')
        f2.write(lineHeading + '\n')

        # Print Headings
        Head1 = 'Date & Time'.ljust(30)[:30]
        Head2 = 'Event Description'.ljust(40)[:40]
        Head3 = 'Value'.ljust(10)[:10]
        f2.write(Head1 + Head2 + Head3 + '\n')
        f2.write(lineHeading2 + '\n')

        for dataLine in range(len(myList) - 1):
            # Extract report data
            Data1 = myList[dataLine][1].ljust(30)[:30]
            Data2 = myList[dataLine][4].ljust(40)[:40]
            Data3 = myList[dataLine][6].ljust(10)[:10]

            # Print it
            f2.write(Data1 + Data2 + Data3 + '\n')

        f2.write(lineHeading + '\n' + '\n')
        f2.close()
        indigo.server.log('** Setpoint Data Report Completed **')

    ########################################
    #  Thermostat Action callback
    ######################
    # Main thermostat action bottleneck called by Indigo Server.

    def actionControlThermostat(self, action, dev):
        global nestDebug

        nestField = dev.states['temperature_scale'].lower()
        nestCurrentTarget = dev.states["target_temperature_" + nestField]
        nestHvac = dev.states["hvac_mode"]

        if nestHvac == 'heat-cool':
            nestCurrentTargetCool = dev.states["target_temperature_high_" + nestField]
            nestCurrentTargetHeat = dev.states["target_temperature_low_" + nestField]
        else:
            nestCurrentTargetCool = nestCurrentTarget
            nestCurrentTargetHeat = nestCurrentTarget

        ###### SET HVAC MODE ######
        if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            nestChangeHvac = self._handleChangehvacOperationModeAction(dev, action.actionMode)
            if nestChangeHvac:
                dev.updateStateOnServer("hvacOperationMode", action.actionMode)

                # Refresh the states in the dialog
                nestUpdate = []
                nestKeyFieldUpdate(dev)

                # Force a set points update for change in mode
                nestSecure = self.pluginPrefs.get('nestAuthorisation', "")
                nestAPI = setupAPI(False)
                nestMap = nestMapping(nestSecure, False)
                if nestMap[0]:
                    refreshNests(nestMap[1], nestAPI[0], nestAPI[1], False)
                else:
                    if nestDebug:
                        indigo.server.log(u'Failed to update API from Nests - SET HVAC')

        ###### SET FAN MODE ######
        elif action.thermostatAction == indigo.kThermostatAction.SetFanMode:
            self._handleChangeFanModeAction(dev, action.actionMode)
            dev.updateStateOnServer("hvacFanMode", action.actionMode)

        ###### SET COOL SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
            # Must be in cool or heat-cool mode
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'cool') and dev.states['can_cool']:
                newSetpoint = action.actionValue
                if dev.states['hvac_mode'] == 'heat-cool':
                    nestScale = dev.states['temperature_scale'].lower()
                    nestField = 'target_temperature_low_' + nestScale
                    if newSetpoint - dev.states[nestField] < 3:
                        # Adjust Heat Setpoint to accomodate the Cool Setpoint
                        # Just make sure that you're not exceeding the Minimum
                        if nestScale.upper() == 'F':
                            nestMin = 50
                        else:
                            nestMin = 9

                        # Now check values and adjust to max or min values
                        if newSetpoint - 3 < nestMin:
                            # Reject Change
                            if nestDebug:
                                indigo.log(
                                    'Decrease in Cool Set point rejected as Heat Set point would lower than minimum')
                            return

                        # Make the changes
                        self._handleChangeSetpointAction(dev, newSetpoint - 3, u"decrease heat setpoint",
                                                         u"setpointHeat")
                        nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                        dev.updateStateOnServer("setpointHeat", newSetpoint - 3, uiValue=nestTempUI % (newSetpoint - 3))

                self._handleChangeSetpointAction(dev, newSetpoint, u"change cool setpoint", u"setpointCool")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointCool", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        ###### SET HEAT SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'heat') and dev.states['can_heat']:
                newSetpoint = action.actionValue
                if dev.states['hvac_mode'] == 'heat-cool':
                    nestScale = dev.states['temperature_scale'].lower()
                    nestField = 'target_temperature_high_' + nestScale
                    if dev.states[nestField] - newSetpoint < 3:
                        # Adjust Cool Setpoint to accomodate increase in Heat Setpoint
                        # Just make sure that you're not exceeding the Maximum
                        if nestScale.upper() == 'F':
                            nestMax = 90
                        else:
                            nestMax = 32

                        # Now check values and adjust to max or min values
                        if newSetpoint + 3 > nestMax:
                            # Reject Change
                            if nestDebug:
                                indigo.server.log(
                                    'Change in Heat Set point rejected as Cool Set point would higher than maximum')
                            return

                        # Make the changes
                        self._handleChangeSetpointAction(dev, newSetpoint + 3, u"increase cool setpoint",
                                                         u"setpointCool")
                        nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                        dev.updateStateOnServer("setpointCool", newSetpoint + 3, uiValue=nestTempUI % (newSetpoint + 3))

                self._handleChangeSetpointAction(dev, newSetpoint, u"change heat setpoint", u"setpointHeat")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointHeat", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        ###### DECREASE/INCREASE COOL SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'cool') and dev.states['can_cool']:
                newSetpoint = nestCurrentTargetCool - action.actionValue
                if dev.states['hvac_mode'] == 'heat-cool':
                    nestScale = dev.states['temperature_scale'].lower()
                    nestField = 'target_temperature_low_' + nestScale
                    if newSetpoint - dev.states[nestField] < 3:
                        # Adjust Heat Setpoint to accomodate increase in Cool Setpoint
                        # Just make sure that you're not exceeding the Maximum
                        if nestScale.upper() == 'F':
                            nestMin = 50
                        else:
                            nestMin = 9

                        # Now check values and adjust to max or min values
                        if newSetpoint - 3 < nestMin:
                            # Reject Change
                            if nestDebug:
                                indigo.server.log(
                                    'Decrease in Cool Set point rejected as Heat Set point would lower than minimum')
                            return

                        # Make the changes
                        self._handleChangeSetpointAction(dev, newSetpoint - 3, u"decrease heat setpoint",
                                                         u"setpointHeat")
                        nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                        dev.updateStateOnServer("setpointHeat", newSetpoint - 3, uiValue=nestTempUI % (newSetpoint - 3))

                self._handleChangeSetpointAction(dev, newSetpoint, u"decrease cool setpoint", u"setpointCool")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointCool", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'cool') and dev.states['can_cool']:
                newSetpoint = nestCurrentTargetCool + action.actionValue
                self._handleChangeSetpointAction(dev, newSetpoint, u"increase cool setpoint", u"setpointCool")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointCool", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        ###### DECREASE/INCREASE HEAT SETPOINT ######
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'heat') and dev.states['can_heat']:
                newSetpoint = nestCurrentTargetHeat - action.actionValue

                self._handleChangeSetpointAction(dev, newSetpoint, u"decrease heat setpoint", u"setpointHeat")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointHeat", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            if (dev.states['hvac_mode'] == 'heat-cool' or dev.states['hvac_mode'] == 'heat') and dev.states['can_heat']:
                newSetpoint = nestCurrentTargetHeat + action.actionValue
                if dev.states['hvac_mode'] == 'heat-cool':
                    nestScale = dev.states['temperature_scale'].lower()
                    nestField = 'target_temperature_high_' + nestScale
                    if dev.states[nestField] - newSetpoint < 3:
                        # Adjust Cool SetPoint to accomodate decrease in Heat Setpoint
                        # Just make sure that you're not above the maximum
                        if nestScale.upper() == 'F':
                            nestMax = 90
                        else:
                            nestMax = 32

                        # Now check values and adjust to max or min values
                        if newSetpoint + 3 > nestMax:

                            # Reject Change
                            if nestDebug:
                                indigo.server.log(
                                    'Increase in Heat Set point rejected as Cool Set point would be above maximum')
                            return

                        # Make the changes
                        self._handleChangeSetpointAction(dev, newSetpoint + 3, u"increase cool setpoint",
                                                         u"setpointCool")
                        nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                        dev.updateStateOnServer("setpointCool", newSetpoint + 3, uiValue=nestTempUI % (newSetpoint + 3))

                self._handleChangeSetpointAction(dev, newSetpoint, u"increase heat setpoint", u"setpointHeat")
                nestTempUI = "%.1f " + dev.states['temperature_scale'].upper()
                dev.updateStateOnServer("setpointHeat", newSetpoint, uiValue=nestTempUI % (newSetpoint))

        ###### REQUEST STATE UPDATES ######
        elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll,
                                         indigo.kThermostatAction.RequestMode,
                                         indigo.kThermostatAction.RequestEquipmentState,
                                         indigo.kThermostatAction.RequestTemperatures,
                                         indigo.kThermostatAction.RequestHumidities,
                                         indigo.kThermostatAction.RequestDeadbands,
                                         indigo.kThermostatAction.RequestSetpoints]:
            self._refreshStatesFromHardware(dev)

    ########################################
    # Sensor Action callback
    ######################
    def actionControlSensor(self, action, dev):
        ###### TURN ON ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        if action.sensorAction == indigo.kSensorAction.TurnOn:
            if nestDebug:
                indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "on"))

        ###### TURN OFF ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        elif action.sensorAction == indigo.kSensorAction.TurnOff:
            if nestDebug:
                indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "off"))

        ###### TOGGLE ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        elif action.sensorAction == indigo.kSensorAction.Toggle:
            if nestDebug:
                indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "toggle"))

    ########################################
    # General Action callback
    ######################

    def profenceAssign(self, valuesDict, typeId, devId):
        if 'proFence' in valuesDict:
            dev = indigo.devices[devId]
            geo = int(valuesDict['proFence'])

            if geo == 0:
                # No Active GeoFence Found so return
                return

            geoFence = indigo.devices[geo]
            dev.updateStateOnServer('proAssignId', str(geoFence.id))
            dev.updateStateOnServer('proAssignName', geoFence.name)
            dev.updateStateOnServer('proNESTRange', int(geoFence.states['devicesInNestRange']))
            dev.updateStateOnServer('proNearRange', int(geoFence.states['devicesNear']))

        else:
            indigo.server.log('ProGeo Not Found!')

    def geofenceAssign(self, valuesDict, typeId, devId):
        if 'geoFence' in valuesDict:
            dev = indigo.devices[devId]
            geo = int(valuesDict['geoFence'])

            if geo == 0:
                # No Active GeoFence Found so return
                return

            geoFence = indigo.devices[geo]
            dev.updateStateOnServer('geoAssignId', str(geoFence.id))
            dev.updateStateOnServer('geoAssignName', geoFence.name)
            dev.updateStateOnServer('geoNESTRange', int(geoFence.states['devicesInNestRange']))
            dev.updateStateOnServer('geoNearRange', int(geoFence.states['devicesNear']))

        return

    def myActiveGeos(self, filter="", valuesDict=None, typeId="", targetId=0):
        global gFindStuff

        # Is iFindStuff running?
        if not gFindStuff:
            # iFindStuff isn't running so tell user
            indigo.server.log('GeoFences cannot be assigned - run iFindStuff and try again')
            return

        # Create an array where each entry is a list - the first item is
        # the value attribute and last is the display string that will be shown
        # Active Devices Only filter
        gTempKeys = {}
        iDeviceArray = []
        for dev in indigo.devices.iter('com.corporatechameleon.iFindplugBeta.iGeoFence'):
            # Only list active devices
            if 'geoActive' in dev.globalProps['com.corporatechameleon.iFindplugBeta']:
                geoActive = dev.globalProps['com.corporatechameleon.iFindplugBeta']['geoActive']

            if 'geoNEST' in dev.globalProps['com.corporatechameleon.iFindplugBeta']:
                geoNEST = dev.globalProps['com.corporatechameleon.iFindplugBeta']['geoNEST']

            if geoActive and geoNEST:
                # It's active and its a NEST GeoFence
                if dev.configured and dev.enabled:
                    # Get Details and store them
                    # Create value & option display
                    iOption = dev.id, dev.name
                    iDeviceArray.append(iOption)

        if len(iDeviceArray) == 0:
            iOption = 0, 'No Active NEST Geos Found'
            iDeviceArray.append(iOption)

        return iDeviceArray

    def actionControlGeneral(self, action, dev):
        ###### BEEP ######
        if action.deviceAction == indigo.kDeviceGeneralAction.Beep:
            # Beep the hardware module (dev) here:
            # ** IMPLEMENT ME **
            if nestDebug:
                indigo.server.log(u"sent \"%s\" %s" % (dev.name, "beep request"))

        ###### ENERGY UPDATE ######
        elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyUpdate:
            # Request hardware module (dev) for its most recent meter data here:
            # ** IMPLEMENT ME **
            if nestDebug:
                indigo.server.log(u"sent \"%s\" %s" % (dev.name, "energy update request"))

        ###### ENERGY RESET ######
        elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyReset:
            # Request that the hardware module (dev) reset its accumulative energy usage data here:
            # ** IMPLEMENT ME **
            if nestDebug:
                indigo.server.log(u"sent \"%s\" %s" % (dev.name, "energy reset request"))

        ###### STATUS REQUEST ######
        elif action.deviceAction == indigo.kDeviceGeneralAction.RequestStatus:
            # Query hardware module (dev) for its current status here. This differs from the
            # indigo.kThermostatAction.RequestStatusAll action - for instance, if your thermo
            # is battery powered you might only want to update it only when the user uses
            # this status request (and not from the RequestStatusAll). This action would
            # get all possible information from the thermostat and the other call
            # would only get thermostat-specific information:
            # ** GET BATTERY INFO **
            # and call the common function to update the thermo-specific data
            self._refreshStatesFromHardware(dev)
            if nestDebug:
                indigo.server.log(u"sent \"%s\" %s" % (dev.name, "status request"))

    ########################################
    # Custom Plugin Action callbacks (defined in Actions.xml)
    ######################
    def getNestPIN(self, nestDict):
        # Generates a PIN from a NEST API Client
        nestURL = 'https://home.nest.com/login/oauth2?client_id=b54e388d-2a1a-4039-9689-849dd636821b&state=STATE'

        # Open the browser to let the user login and get their PIN code
        try:
            webbrowser.open(nestURL)

        except:
            errorHandler('getNestPIN')
            indigo.server.log('home.nest.com website not responding... Do you have an intenet connection?',
                              isError=True)

    def getNestAPI(self, nestDict):
        # Generates a key from a valid PIN by constructing an access token URL with the PIN
        nestPIN = nestDict['nestPIN']

        if len(nestPIN) == 0:
            indigo.server.log('Enter your PIN Code before getting an API key')
        else:
            # Let's get the key (These keys are for the Corporate Chameleon Indigo Client - good for 1000 users)
            nestAPI1 = 'https://api.home.nest.com/oauth2/access_token?client_id=b54e388d-2a1a-4039-9689-849dd636821b&code='
            nestAPI2 = '&client_secret=kK3QlQ9EI87PnGTBxeE27U4ui&grant_type=authorization_code'
            nestCommand = "curl -X POST " + "'" + nestAPI1 + nestPIN + nestAPI2 + "'"
            nestKey = subprocess.Popen([nestCommand], stdout=subprocess.PIPE, shell=True)
            nestKey.wait()
            nestAPIResponse = nestKey.communicate()
            nestAPIDict = ast.literal_eval(nestAPIResponse[0])

            # Extract the token and store it in the Configuration
            try:
                nestAPI = nestAPIDict['access_token']
                nestDict['nestAuthorisation'] = nestAPI
                nestFolder = self.pluginPrefs.get('nestTxt')

                return nestDict

            except KeyError:
                indigo.server.log(
                    'API key not created - have you entered the PIN correctly? - Error:' + nestAPIDict['error'])
                nestDict['nestAuthorisation'] = ''

    def setAwayStatus(self, pluginAction, dev):
        try:
            newAwayStatus = pluginAction.props.get(u"awayPopUp")
            self.debugLog(newAwayStatus)
            newDisplayStatus = newAwayStatus.capitalize()
            nestStructureKey = self.pluginPrefs["structure_key"]

        except ValueError:
            return False

        # Update the Actual Nest Configuration
        try:
            nestSecure = self.pluginPrefs["nestAuthorisation"]
            updateSuccess = nestUpdateField(nestSecure, 'structures', nestStructureKey, dev.states['nestHomeName'],
                                            "away", newAwayStatus.lower())

            indigo.server.log('Away success:' + str(updateSuccess))

        except:
            errorHandler('setAwayStatus')

            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                indigo.server.log(
                    u"send \"%s\" %s to %s failed" % (dev.name, "Nest away status", newAwayStatus.capitalize()))

            return False

        # Now align the Master Device as the real Nest is updated
        try:
            updateSuccess = dev.updateStateOnServer(u'nestAway', newAwayStatus.capitalize())
            if nestShowC:
                indigo.server.log(u"sent \"%s\" %s to %s" % (dev.name, "change AWAY setting", newDisplayStatus))

        except:
            # Else log failure but do NOT update state on Indigo Server.
            errorHandler('setAwayStatus')
            if nestDebug:
                self.debugLog(
                    "send \"%s\" %s to %s failed" % (dev.name, "change AWAY setting", newAwayStatus.capitalize()))
            return False

        # Align the PluginProps
        try:
            nestPropsField = 'nestAway'
            self.pluginPrefs[nestPropsField] = newAwayStatus.capitalize()
            return True

        except:
            errorHandler('setAwayStatus')
            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                indigo.server.log(
                    u"send \"%s\" %s to %s failed" % (dev.name, "Nest away status", newAwayStatus.capitalize()))
            return False

    def setFanDuration(self, pluginAction, dev):
        if not dev.states['has_fan']:
            # This device doesn't have a fan so advise the user
            indigo.server.log(u'ERROR: The device ' + dev.states[
                'name_long'] + u" doesn't appear to have an independent fan.  Is it connected?")
            return

        try:
            newFanStatus = pluginAction.props.get(u"fanDuration")
            self.debugLog(newFanStatus)
            newDisplayStatus = newFanStatus.capitalize()
            nestThermoKey = dev.states["device_id"]

        except ValueError:
            errorHandler('setFanDuration')
            return False

        # Update the Actual Nest Configuration
        try:
            nestSecure = self.pluginPrefs["nestAuthorisation"]
            updateSuccess = nestUpdateField(nestSecure, 'thermostats', nestThermoKey, dev.states['name_long'],
                                            "fan_timer_duration", newFanStatus)

        except:
            errorHandler('setFanDuration')
            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                indigo.server.log(u"send \"%s\" %s to %s failed" % (dev.name, "Nest fan duration", newFanStatus))

            return False

        # Now align the Thermostat Device as the real Nest is updated
        try:
            updateSuccess = dev.updateStateOnServer(u'fan_timer_duration', newFanStatus)
            if nestShowC:
                indigo.server.log(u"sent \"%s\" %s to %s" % (dev.name, "change Fan Duration", newDisplayStatus))

        except:
            errorHandler('setFanDuration')
            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                self.debugLog("send \"%s\" %s to %s failed" % (dev.name, "change Fan duration", newFanStatus))
            return False


    def setFanStatus(self, pluginAction, dev):
        if not dev.states['has_fan']:
            # This device doesn't have a fan so advise the user
            indigo.server.log(u'ERROR: The device ' + dev.states[
                'name_long'] + u" doesn't appear to have an independent fan.  Is it connected?")
            return

        try:
            newFanStatus = pluginAction.props.get(u"fanPopUp")
            self.debugLog(newFanStatus)
            newDisplayStatus = newFanStatus.capitalize()
            nestThermoKey = dev.states["device_id"]

        except ValueError:
            errorHandler('setFanStatus')
            return False

        # Update the Actual Nest Configuration
        try:
            nestSecure = self.pluginPrefs["nestAuthorisation"]
            updateSuccess = nestUpdateField(nestSecure, 'thermostats', nestThermoKey, dev.states['name_long'],
                                            "fan_timer_active", newFanStatus)

        except:
            errorHandler('setFanStatus')
            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                indigo.server.log(u"send \"%s\" %s to %s failed" % (dev.name, "Nest fan status", newFanStatus))

            return False

        # Now align the Thermostat Device as the real Nest is updated
        try:
            updateSuccess = dev.updateStateOnServer(u'fan_timer_active', newFanStatus)
            if nestShowC:
                indigo.server.log(u"sent \"%s\" %s to %s" % (dev.name, "change Fan setting", newDisplayStatus))

        except:
            errorHandler('setFanStatus')
            # Else log failure but do NOT update state on Indigo Server.
            if nestDebug:
                self.debugLog("send \"%s\" %s to %s failed" % (dev.name, "change Fan setting", newFanStatus))
            return False

    ########################################
    # Actions defined in MenuItems.xml. In this case we just use these menu actions to
    # simulate different thermostat configurations (how many temperature and humidity
    # sensors they have).
    ####################
    def changeTempSensorCountTo1(self):
        self._changeAllTempSensorCounts(1)

    def changeTempSensorCountTo2(self):
        self._changeAllTempSensorCounts(2)

    def changeTempSensorCountTo3(self):
        self._changeAllTempSensorCounts(3)

    def changeHumiditySensorCountTo0(self):
        self._changeAllHumiditySensorCounts(0)

    def changeHumiditySensorCountTo1(self):
        self._changeAllHumiditySensorCounts(1)

    def changeHumiditySensorCountTo2(self):
        self._changeAllHumiditySensorCounts(2)

    def changeHumiditySensorCountTo3(self):
        self._changeAllHumiditySensorCounts(3)

    def nestDisplay(self):
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])
        nestAPI = setupAPI(False)
        nestMap = nestMapping(nestSecure)
        if nestMap[0]:
            nestCustom = nestCustomAPI(False)
            displayMap(nestMap[1], nestAPI[0], nestAPI[1], nestCustom[0], nestCustom[1])
        else:
            if nestDebug:
                indigo.server.log(u'Failed to access API - NEST DISPLAY')

    def nestPrint(self):
        nestSecure = str(self.pluginPrefs["nestAuthorisation"])
        nestFolder = self.pluginPrefs["nestTxt"]
        nestAPI = setupAPI(False)
        nestMap = nestMapping(nestSecure)
        if nestMap[0]:
            nestCustom = nestCustomAPI(False)
            printMap(nestMap[1], nestAPI[0], nestAPI[1], nestCustom[0], nestCustom[1], nestFolder)
        else:
            if nestDebug:
                indigo.server.log(u'Failed to access API - NEST PRINT')
