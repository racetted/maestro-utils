#!/usr/bin/env python
 
#/* Part of the Maestro sequencer software package.
# * Copyright (C) 2011-2015  Operations division of the Canadian Meteorological Centre
# *                          Environment Canada
# *
# * Maestro is free software; you can redistribute it and/or
# * modify it under the terms of the GNU Lesser General Public
# * License as published by the Free Software Foundation,
# * version 2.1 of the License.
# *
# * Maestro is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# * Lesser General Public License for more details.
# *
# * You should have received a copy of the GNU Lesser General Public
# * License along with this library; if not, write to the
# * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# * Boston, MA 02111-1307, USA.
# */

# Author: 
#           CMOIS 
# Revision: 
#           1.0 July 14, 2010  -  first draft
# Description:
#           Builds the flow of an experiment based on the contained modules


from xml.dom.minidom      import parse
import os
import sys
import optparse

debug=False

def main():    

    #
    # OBTAIN THE COMMAND-LINE ARGUMENTS
    #

    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-e","--exp_path",dest="expPath",default=os.getenv('SEQ_EXP_PATH'),
                      help="Full experiment PATH (default SEQ_EXP_PATH)",metavar="PATH")
    parser.add_option("-o","--output",dest="outFileName",default=None,
                      help="Output xml FILE containing the full xml flow, default will be stdout",metavar="FILE")
    (options,args) = parser.parse_args()
    
    entryXmlFile = options.expPath+'/EntryModule/flow.xml'
    outputXmlDocument = recursiveParseXml(entryXmlFile,options.expPath)
    outputXml(outputXmlDocument,options.outFileName)
  
#
# Recursive command to build the XML tree
#      xmlFile: path to the xml file to open
#      expPath: path of the experiment
def recursiveParseXml(xmlFileName, expPath ):

	#open the new xml 
	currentDocumentXml = parse(xmlFileName)
	if debug: print "currentDocumentXml's headnode is " + currentDocumentXml.documentElement.getAttribute("name") 
	#checks for module tags to load the subjacent flow files
	for moduleIterator in currentDocumentXml.getElementsByTagName("MODULE"):

	        if debug: print "At for loop, moduleIterator=" + moduleIterator.getAttribute("name")
                # check if the iterator is at the current top node (which we won't need to do anything with)
		if moduleIterator != currentDocumentXml.documentElement:

		        #filename of the module's xml file to recursively open
			newXmlFileName = expPath+'/modules/'+moduleIterator.getAttribute("name")+'/flow.xml'
			childDocumentXml = recursiveParseXml(newXmlFileName, expPath)

			#put the child's flow inside the insertion point 
			if debug: print "Replacing "+ moduleIterator.getAttribute("name")+ " with "+childDocumentXml.documentElement.getAttribute("name")  
			#grab the child's headnode and import it in the current document
		        nodesToAppend = currentDocumentXml.importNode(childDocumentXml.documentElement, True)
			#and replace the current module's node with the child's  
			moduleIterator.parentNode.insertBefore(nodesToAppend,moduleIterator)
                        moduleIterator.parentNode.removeChild(moduleIterator)

	return currentDocumentXml
##
## Function to output the xml document with the options provided
##


def outputXml(xmlDocument, outputFileName):

        # output to a file or stdout
        if outputFileName == None: 
             print xmlDocument.toprettyxml()
	else:
	     try:
	         outputFile = open(outputFileName, 'w')
	         xmlDocument.writexml(outputFile)
	         outputFile.close()
             except IOError:
	         print "flowbuilder.py ERROR: could not create " + outputFileName
		 sys.exit(1)

	xmlDocument.unlink();


if __name__ == "__main__":
    main()
