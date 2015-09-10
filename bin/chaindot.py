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


"""This utility effects what is known as 'dotting down the chain'.  That means
that it ingests the flow of an experiment (from the flow.xml file) and identifies
a branch therein according to the supplied path.  It then follows down that
branch, dotting the configuration files (*.cfg) that it finds along the way.

INPUT:
     - absolute path to the experiment directory, excluding the final directory
       which would be the experiment name
     - chain of experiment nodes, beginning with the experiment name and
       terminating with the node whose context is being constructed

The content of the experiment directory defines the experiment in question.  It
is assumed that the directory has this form (This is a minimum; other elements
may also be present):
    MyExpt
        experiment.cfg
        flow.xml
        resources
            resources.cfg
        modules
            module_1
                module_1.cfg
                family_1
                    family_1.cfg
                    task_1
                        task_1.cfg
            module_n
                module_n*.cfg

A *.cfg may or may not exist for each node in the supplied path.

Each line of the *.cfg files is of the form,
    type MyVarName=MyVarValue
where type must be one of:
    interface
    private
    public

Private variables are effective from the point where they are declared and
downwards along the branch up to the next module-node.

The scope of interface variables is identical to that of private variables,
except that their value is taken from those that were available one node upward.
This is important where the current node is a module-node; a private variable
from the previous node would be already out of scope, but an interface variable
of the same name has the power to access that out-of-scope value.  Thus,
interface variables are useful for receiving information in one module from the
previous module.
    
Public variables are effective from the point where they are declared and
downwards all the way along the branch.  It should be noted that a public
variable may be hidden by a private or interface variable, but will be visible
again beyond the scope of the hiding private or interface variable.

This is a prototype of a utility that will ultimately be used with the
unified sequencer."""

#
# AUTHOR
#     J.W. Blezius

#REVISION
# v1_00   Blezius J.W.    May 20 2009 first release
# v1_01   Racette D.      July 14 2010 Modified argument passing
# v1_02   Racette D.      July 21 2010 Modified experiment structure
# v1_03   Racette D.      Aug. 24 2010 Removing Scoping
# v1_04   Racette D.      Nov. 20 2010 Changed loop behaviour
# v1_10   McTaggart-Cowan R. July 2012 Add resource file sourcing
#         Racette D.      Oct 2012     Clarified output, added MODULE_ARGUMENTS files 


from xml.dom              import expatbuilder
from xml.dom              import Node
from xml.dom.minidom      import parse
import os
import sys
import optparse
import subprocess

l_debug = False
errorFlag = False

class T_Chain:
    """This class does just one thing:  it follows down the chain of nodes,
    dotting configuration files along the way.  It simply encapsulates the
    methods that accomplish this."""

    def __init__(self, s_exptPath, s_NodePath, s_outFileName):
                                        # path to the experiment directory
        self.s_exptPath = s_exptPath        
        self.s_exptName = os.path.realpath(s_exptPath).split('/')[-1]
        self.s_currentNodeDir =''     # string: directory of current node
        self.s_currentContainer =''
                                        # list: node-path in expt to sought node
        self.o_tree_List = s_NodePath.split('/')
        self.o_tree_List=[self.s_exptName]+self.o_tree_List
        self.s_prevModuleName=''

        self.s_NodeName = self.o_tree_List[-1]

                                        # Digest the node sought
        if l_debug: print 's_NodePath=', s_NodePath

        #
        # Recursively read the flow.xml file for each module of the tree
        #
        entryXmlFile = s_exptPath + '/EntryModule/flow.xml'
        o_xmlDocument = self.recursiveParseXml(entryXmlFile)

                                        # Read the flow.xml
                                        # (This permits identifying the modules)
        self.o_node = o_xmlDocument.documentElement

        #
        # Open the output file, to be dotted by the client
        #
        self.s_pwd = os.getenv('PWD')
        try:
            self.o_dotout = s_outFileName and open(s_outFileName, 'w') or sys.stdout
        except IOError:
            sys.stderr.write("Error: unable to open "+s_outFileName+" for writing\n")
            sys.exit(1)
    
    def recursiveParseXml(self, xmlFileName):
        #open the new xml 
        currentDocumentXml = parse(xmlFileName)
        if l_debug: print "recursiveParseXml: currentDocumentXml's headnode is " + currentDocumentXml.documentElement.getAttribute("name") 
        #checks for module tags to load the subjacent flow files
        for moduleIterator in currentDocumentXml.getElementsByTagName("MODULE"):

            if l_debug: print "recursiveParseXml: At for loop, moduleIterator=" + moduleIterator.getAttribute("name")
            # check if the iterator is at the current top node (which we won't need to do anything with)
            if moduleIterator != currentDocumentXml.documentElement:
   
                #filename of the module's xml file to recursively open
                newXmlFileName = self.s_exptPath + '/modules/' + moduleIterator.getAttribute("name")+'/flow.xml'
                childDocumentXml = self.recursiveParseXml(newXmlFileName)
                #put the child's flow inside the insertion point 
                if l_debug: print "recursiveParseXml: Replacing "+ moduleIterator.getAttribute("name")+ " with "+childDocumentXml.documentElement.getAttribute("name")  
                if l_debug: print "recursiveParseXml: Renaming "+ childDocumentXml.documentElement.getAttribute("name") + " to " +   moduleIterator.getAttribute("name") + " in child module." 
                childDocumentXml.documentElement.setAttribute("name", moduleIterator.getAttribute("name"))
                #grab the child's headnode and import it in the current document
                nodesToAppend = currentDocumentXml.importNode(childDocumentXml.documentElement, True)
                #and replace the current module's node with the child's  
                moduleIterator.parentNode.insertBefore(nodesToAppend,moduleIterator)
                moduleIterator.parentNode.removeChild(moduleIterator)

        return currentDocumentXml
    
    def DotTheChain(self):
        """To the *.dot file, write the necessary shell commands to set the
        variables."""    
        #
        # Establish the starting point of the chain
        #
        is_stdout = self.o_dotout.name is sys.stdout.name
        #experiment config
        self.__dotCfg(self.o_tree_List[0], "EXPERIMENT", is_stdout )

        # Advance to first node name sought
        self.o_tree_List = self.o_tree_List[1:]

        #first module config
        self.__dotCfg(self.o_tree_List[0], self.o_node.tagName, is_stdout )
                                        # Advance to first node name sought
        self.s_prevModuleName=self.o_tree_List[0]
        self.o_tree_List = self.o_tree_List[1:]

        #
        # Dot the chain down to the node in question
        #
        while self.o_tree_List:

            # Search the children

            l_ChildFound=False
            for o_child in self.o_node.childNodes:
                if o_child.nodeType != Node.ELEMENT_NODE:
                    continue

                                        # Is this the sought child?
                if self.o_tree_List[0] == o_child.getAttribute('name'):
                    l_ChildFound=True

                    if  (self.s_prevModuleName != ''):
                        # Dot the internal module configuration 
                        self.__dotCfg(self.s_prevModuleName, "MODULE_INTERNALS", is_stdout)
 			self.s_prevModuleName=''

                    if  (o_child.tagName == "MODULE"):
                        self.s_prevModuleName=self.o_tree_List[0]
                        self.__dotCfg(self.o_tree_List[0],"MODULE_ARGUMENTS",is_stdout)

                    # Dot the configuration for this link in the chain
                    self.__dotCfg(self.o_tree_List[0], o_child.tagName, is_stdout)

                    # Advance to the node just found
                    self.o_node = o_child
 
                    if  (o_child.tagName == "SWITCH"):
                        #advance to resulting node of switch
                        switch_item_found = 0;
                        answer=str(self.__switchAnswer(o_child.getAttribute('type')))
                        print("Switch found, answer=" + answer)
                        for o_child_answer in self.o_node.childNodes:
                            if o_child_answer.nodeType != Node.ELEMENT_NODE:
                                continue
                            if (o_child_answer.getAttribute('name') == answer):
			        switch_item_found = 1
                                self.o_node = o_child_answer
                            #if no exact match, search for switch item within multiple values
                            else:
                                tmp_name = o_child_answer.getAttribute('name')
                                name_list = tmp_name.split(',')
                                for single_name in name_list:
				    if single_name == answer:
				        switch_item_found = 1
				        self.o_node = o_child_answer
			#if no match, search for default switch item
			if switch_item_found == 0:
			    for o_child_answer in self.o_node.childNodes:
                                if o_child_answer.nodeType != Node.ELEMENT_NODE:
                                    continue
				if (o_child_answer.getAttribute('name') == 'default'):
				    switch_item_found = 1
				    self.o_node = o_child_answer
			        
                    # Advance to the next node name sought
                    self.o_tree_List = self.o_tree_List[1:]
                    break    

            assert l_ChildFound, "In flow.xml the child, "+ self.o_tree_List[0] + \
                                 ", not found below "+ \
                                 self.o_node.getAttribute('name')

        if l_debug: print 'sought node=', self.o_node.tagName, \
                          self.o_node.getAttribute('name')

        # Move the dot file to its final destination
        if not is_stdout:
            self.o_dotout.close()

    def __dotCfg(self, s_cfg, s_nodeType, is_stdout):
        """To dot a single configuration file in the chain, write to the *.dot
        file the necessary shell commands to set the variables.  In addition,
        track the private and interface variables and add any commands required
        by these."""

        s_pathCfg=[] 
        s_nodeType = s_nodeType.upper() # Ensure upper case

        if l_debug: print "in dotCfg, s_cfg=", s_cfg, "\n", \
                          "           s_nodeType=", s_nodeType
 
        if (s_nodeType == 'MODULE'):    # If this is a new module
                                        # Reset the config-file path
            self.s_currentNodeDir = 'modules'

        # Construct the path to the configuration file
	
	#skip out loops if included in the node path
	if  s_nodeType == 'TASK' or s_nodeType == 'NPASS_TASK':
	    s_pathCfg = [os.path.join(self.s_exptPath, self.s_currentNodeDir, s_cfg + '.cfg')]
        elif s_nodeType == 'EXPERIMENT':
            s_pathCfg = [os.path.join(self.s_exptPath, 'experiment.cfg')]
        elif s_nodeType == 'MODULE_ARGUMENTS':
            s_pathCfg = [os.path.join(self.s_exptPath, self.s_currentNodeDir, s_cfg + '.cfg')]
        elif s_nodeType == 'MODULE_INTERNALS':
            s_pathCfg = [os.path.join(self.s_exptPath, self.s_currentNodeDir,'internal.var')]
        else: ## container
            self.s_currentNodeDir =  os.path.join(self.s_currentNodeDir, s_cfg)
            s_pathCfg = s_pathCfg + [os.path.join(self.s_exptPath, self.s_currentNodeDir, 'container.cfg')]
            
        for cfgFile in s_pathCfg:            
            
            if not is_stdout:
                self.o_dotout.write('\n## <CONFIG type=\"' + s_nodeType +'\" name=\"' + s_cfg + '\" path=\"'+ cfgFile + '\" > \n')
            if s_nodeType == 'FAMILY' or s_nodeType == 'LOOP' or s_nodeType == 'SWITCH' or s_nodeType == 'MODULE':
                self.s_currentContainer=self.s_currentContainer + "/" + s_cfg
                self.o_dotout.write("SEQ_CURRENT_CONTAINER=" + self.s_currentContainer + "\n")
            if s_nodeType == 'MODULE':
                self.o_dotout.write("SEQ_CURRENT_MODULE=" + s_cfg + "\n")
            try:
                o_cfgFile = open(cfgFile, 'r')
                s_input=o_cfgFile.readlines()
                o_cfgFile.close()
                for s_line in s_input:
                    s_line.lstrip()             # Ignore initial white space
                                            ## Keep only non-comment lines
                    if len(s_line) < 2 :  ##or s_line[0] == '#':
                        continue
                    self.o_dotout.write(s_line)
                self.o_dotout.write('\n')
                    
            except IOError:
                # It appears that this node does not have a cfg file
                if not is_stdout: self.o_dotout.write("# - - - >> Could not open " + cfgFile + "\n")

            if not is_stdout:
                self.o_dotout.write('\n## </CONFIG type=\"' + s_nodeType +'\" name=\"' + s_cfg + '\" path=\"'+ cfgFile + '\" > \n')

##            if (s_nodeType == 'MODULE'):    # If this is a module, load privates as well
##                self.__dotCfg(s_cfg,"MODULE_INTERNALS",is_stdout)

        return()
 
    def __switchAnswer(self, s_switchType):

        if (s_switchType == 'datestamp_hour'):
            try:
                proc = subprocess.Popen([os.getenv('SEQ_BIN') + "/tictac","-f","%H"], stdout=subprocess.PIPE)
                out = proc.stdout.read().rstrip('\n')
            except OSError:
                print("tictac not found. Please load your maestro ssm package.\n")
                sys.exit(1)
        if (s_switchType == "day_of_week"):
            try:
                proc = subprocess.Popen([os.getenv('SEQ_BIN') + "/tictac","-f","%Y%M%D"], stdout=subprocess.PIPE)
                yyyymmdd = proc.stdout.read().rstrip('\n')
                y=int(str(yyyymmdd)[0:4])
                m=int(str(yyyymmdd)[4:6])
                d=int(str(yyyymmdd)[6:8])
            except OSError:
                print("tictac not found. Please load your maestro ssm package.\n")
                sys.exit(1)

            # Sakamoto's algorithm for day of week
            t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
            y -= m < 3
            out=(y + y/4 - y/100 + y/400 + t[m-1] + d) % 7

        return (out)  
    

def main():    

    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-e","--exp_path",dest="expPath",default=os.getenv('SEQ_EXP_HOME'),
                      help="Full experiment PATH (default SEQ_EXP_HOME)",metavar="PATH")
    parser.add_option("-n","--node_path",dest="nodeName",default=None,
                      help="Full PATH to the desired node (mandatory)",metavar="PATH")
    parser.add_option("-o","--output",dest="out",default=None,
                      help="Output dottable FILE containing in-scope variables (default STDOUT)",metavar="FILE")
    (options,args) = parser.parse_args()
    
    # Check for mandatory arguments
    if not options.nodeName:
        sys.stderr.write("Error: a fully-qualified node name (--node_path) is required\n")
        parser.print_help()
        sys.exit(1)
    if not options.expPath:
        sys.stderr.write("Error: SEQ_EXP_PATH and --exp_path (-e) are undefined\n")
        sys.exit(1)
    if not os.path.isdir(options.expPath):
        sys.stderr.write("Error: unable to access "+options.expPath+"\n")
        sys.exit(1)

    MyChain = T_Chain(options.expPath, options.nodeName.lstrip("/"), options.out)
    MyChain.DotTheChain() 

    if errorFlag:
       sys.exit(1)

    
if __name__ == "__main__":
    main()
