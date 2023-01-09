#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2016- Christian Strassburg               c.strassburg@gmx.de
#  Copyright 2017- Serge Wagener                     serge@wagener.family
#  Copyright 2017- Bernd Meiners                    Bernd.Meiners@mail.de
#  Copyright 2019- Thomas Kunze                      Thomas.Kunze@gmx.com
#########################################################################
#  This file is part of SmartHomeNG.py.  
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import struct
import binascii
import random
import time
import knx
import xml.etree.ElementTree as ET
import sys

from lib.item import Items
from lib.model.smartplugin import *
from cherrypy.lib import static

from . import dpts

KNX_DPT      = 'knx_dpt'          # data point type
KNX_STATUS   = 'knx_status'       # status
KNX_SEND     = 'knx_send'         # send changes within SmartHomeNG to this ga
KNX_REPLY    = 'knx_reply'        # answer read requests from knx with item value from SmartHomeNG
KNX_LISTEN   = 'knx_listen'       # write or response from knx will change the value of this item
KNX_POLL     = 'knx_poll'         # query (poll) a ga on knx in regular intervals
KNX_DTP      = 'knx_dtp'          # often misspelled argument in config files, instead should be knx_dpt
KNX_GO       = 'knx_go'
KNX_CACHE    = 'knx_cache'
KNX_INIT     = 'knx_init'


class KnxEts(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.0.0"

    def __init__(self, smarthome):
        from bin.smarthome import VERSION
        self.logger = logging.getLogger(__name__)
        self.sh = smarthome
        self.alive = False
        self.gosRegistered = False

        self.knxprodPath = smarthome.base_dir + '/var/knx_ets/smarthomeNG.xml'
        self.goItemMapping = {}
        self.items = []
        
        args = sys.argv
        args.insert(0, sys.executable)
        knx.Prepare(args)
        
        self.flashFilePath = smarthome.base_dir + '/var/knx_ets/flash.bin'
        self.ensure_dir(self.flashFilePath)
        knx.FlashFilePath(self.flashFilePath)

        ET.register_namespace('',"http://knx.org/xml/project/11")
        ET.register_namespace('xsi',"http://www.w3.org/2001/XMLSchema-instance")
        ET.register_namespace('xsd',"http://www.w3.org/2001/XMLSchema")

        if not self.init_webinterface():
            self._init_complete = False
        
        return

    def ensure_dir(self, file_path):
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def encode(self, data, dpt):
        return dpts.encode[str(dpt)](data)

    def decode(self, data, dpt):
        return dpts.decode[str(dpt)](data)

    def updated(self, groupObject):
        rawValue = groupObject.value
        goNr = groupObject.asap()
     
        item = self.goItemMapping[goNr]

        self.logger.debug("updated " + str(goNr) + " " + str(item) + " #gos " + str(len(item.GroupObjects)))

        if item is None:
            return

        for goNr in item.GroupObjects:
            groupObject = knx.GetGroupObject(goNr)
            if groupObject.asap() != goNr:
                groupObject.value = rawValue 

        dpt = self.get_iattr_value( item.conf, KNX_DPT)
        value = self.decode(rawValue, dpt)

        item(value, "knx_ets")

    def run(self):
        """
        Run method for the plugin
        """
        self.generateKnxProd()

        self.buildGoItemMapping()

        if len(self.goItemMapping) == 0:
            return None

        if len(self.goItemMapping.keys()) != max(self.goItemMapping.keys()):
            self.logger.error("GO-numbers must be continous starting from 1")
            return None
        self.logger.debug(knx.FlashFilePath()) 
        knx.ReadMemory()
        if knx.Configured():
            self.logger.info("knx configured")
            for go in sorted(self.goItemMapping):
                item = self.goItemMapping[go]
                currentGo = knx.GetGroupObject(go)
                
                if not currentGo is None:
                    currentGo.callBack(self.updated)
                if not item is None:
                    item.GroupObjects.append(go)
        else:
            self.logger.info("knx not configured")

        knx.Start()

        self.alive = True


    def stop(self):
        """
        Stop method for the plugin
        """
        knx.Stop()
        self.alive = False


    def parse_item(self, item):
        """
        Plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, KNX_DTP):
            self.logger.error("Ignoring {}: please change knx_dtp to knx_dpt.".format(item))
            return None
        if not self.has_iattr(item.conf, KNX_DPT):
            return None
            
        dpt = self.get_iattr_value( item.conf, KNX_DPT)
        if dpt not in dpts.decode:
            self.logger.warning("Ignoring {} unknown dpt: {}".format(item, dpt))
            return None
        
        item.goCount = 1   
        if self.has_iattr(item.conf, KNX_STATUS):
            item.goCount += 1

        item.GroupObjects = []
        self.items.append(item)
        self.logger.debug("Item {} is mapped to knx_ets({}) with {} groupobjects".format(item, self.get_instance_name(), item.goCount))

        return self.update_item

    def parse_logic(self, logic):
        """
        Plugin parse_logic method
        """
        return None


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated
        
        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that 
        is managed by this plugin.
        
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        self.logger.debug("item {} updated from {}, source {}, dest {}".format(item, caller, source, dest))	
        if not self.alive:
            return None

        if not self.has_iattr(item.conf, KNX_DPT):
            return None
        
        if caller == 'knx_ets':
            return None

        if not knx.Configured():
            return None

        dpt = self.get_iattr_value(item.conf, KNX_DPT)

        value = item()
#        print(value)
        rawValue = bytes(self.encode(value, dpt))
#        print(rawValue)

        for goNr in item.GroupObjects:
            groupObject = knx.GetGroupObject(goNr)
            groupObject.value = rawValue

    def addComObjects(self, root, ComObjectRefs, ComObjectRefRefs, appId):
        nextGoNr = len(root) + 1
        modified = False
        for item in self.items:
            for i in range(item.goCount):
                identifier = str(item.id())
               
                if i > 0:
                    identifier += "_" + str(i)

                commObj = root.find('.//{http://knx.org/xml/project/11}ComObject[@Text="' + identifier + '"]',)
                if not commObj is None:
                    continue

                modified = True
                dpt = self.get_iattr_value(item.conf, KNX_DPT)
                size = dpts.sizes[str(dpt)]
                newElement = ET.Element("ComObject")
                itemName = str(item)
                newElement.set("Name", (itemName[:45] + '..') if len(itemName) > 50 else itemName)
                newElement.set("Number", str(nextGoNr))
                newElement.set("Text", identifier)
                newElement.set("FunctionText", itemName + str(i))
                newElement.set("ObjectSize", dpts.sizenames[str(dpt)])
                newElement.set("DatapointType", "")
                Id=appId + "_O-" + str(nextGoNr)
                newElement.set("Id", Id)
                
                newComObjectRef = ET.Element("ComObjectRef")
                newComObjectRef.set("Id", Id + "_R-" + str(nextGoNr))
                newComObjectRef.set("RefId", Id)
                
                newComObjectRefRef= ET.Element("ComObjectRefRef") 
                newComObjectRefRef.set("RefId", Id + "_R-" + str(nextGoNr))
                

                if self.get_iattr_value(item.conf, KNX_REPLY):
                    newElement.set("ReadFlag", "Enabled")
                else:
                    newElement.set("ReadFlag", "Disabled")

                if (self.get_iattr_value(item.conf, KNX_LISTEN) 
                    or self.get_iattr_value(item.conf, KNX_CACHE) 
                    or self.get_iattr_value(item.conf, KNX_INIT) 
                    or self.get_iattr_value(item.conf, KNX_POLL)):
                    newElement.set("WriteFlag", "Enabled")
                    newElement.set("UpdateFlag", "Enabled")
                else:
                    newElement.set("WriteFlag", "Disabled")
                    newElement.set("UpdateFlag", "Disabled")

                newElement.set("CommunicationFlag", "Enabled")

                if (self.get_iattr_value(item.conf, KNX_SEND)
                    or self.get_iattr_value(item.conf, KNX_STATUS)):
                    newElement.set("TransmitFlag", "Enabled")
                else:
                    newElement.set("TransmitFlag", "Disabled")

                if (self.get_iattr_value(item.conf, KNX_CACHE) 
                    or self.get_iattr_value(item.conf, KNX_INIT)):
                    newElement.set("ReadOnInitFlag", "Enabled")
                else:
                    newElement.set("ReadOnInitFlag", "Disabled")

                root.append(newElement) 
                ComObjectRefs.append(newComObjectRef)
                ComObjectRefRefs.append(newComObjectRefRef)
                
                nextGoNr += 1
        
        return modified

    def indent(self, elem, level=0):
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def generateKnxProd(self):
        sourcePath = self.sh.base_dir + '/plugins/knx_ets/assets/smarthomeNG.xml'

        if os.path.isfile(self.knxprodPath):
            sourcePath = self.knxprodPath

        tree = ET.parse(sourcePath)
        root = tree.getroot()

        appProg = root.find(".//{http://knx.org/xml/project/11}ApplicationProgram")
        appId = appProg.get("Id")

        version = int(appProg.get("ApplicationVersion"))

        comObjs = root.find(".//{http://knx.org/xml/project/11}ComObjectTable")
        ComObjectRefs = root.find(".//{http://knx.org/xml/project/11}ComObjectRefs")
        ComObjectRefRefs = root.find(".//{http://knx.org/xml/project/11}ChannelIndependentBlock")
        
        modified = self.addComObjects(comObjs, ComObjectRefs, ComObjectRefRefs, appId)

        if not modified:
            return

        appProg.set("ApplicationVersion", str(version + 1))
        appProg.set("ReplacesVersions", str(version))

        self.indent(root)
        tree.write(self.knxprodPath, encoding="utf-8", xml_declaration=True)

   #     if os.path.exists(self.flashFilePath):
   #         os.remove(self.flashFilePath)

    def buildGoItemMapping(self):
        tree = ET.parse(self.knxprodPath)
        root = tree.getroot()
        for element in root.findall(".//{http://knx.org/xml/project/11}ComObject"):
            goNr = int(element.get('Number'))
            item = self.sh.return_item(element.get('Text'))
            self.goItemMapping[goNr] = item

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin
        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader

class WebInterface(SmartPluginWebIf):


    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()



    @cherrypy.expose
    def index(self, reload=None, toggleProgramMode = False, getKnxProd = False, deleteConfig = False):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser
        :return: contents of the template after beeing rendered
        """
        if toggleProgramMode:
            knx.ProgramMode(not knx.ProgramMode())

        if getKnxProd:
            #if not os.path.isfile(self.plugin.knxprodPath):
            self.plugin.generateKnxProd()
            return static.serve_file(self.plugin.knxprodPath, 'application/x-download',
                                 'attachment', os.path.basename(self.plugin.knxprodPath))

        if deleteConfig:
            if os.path.exists(self.plugin.flashFilePath):
                os.remove(self.plugin.flashFilePath)

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin)
