#!/usr/bin/env python
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
        MyExpt.cfg
        flow.xml
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


from xml.dom              import expatbuilder
from xml.dom              import Node
import os
import sys
import optparse

l_debug = False
errorFlag = False


def filter_interface((s_var, (s_val, s_type))):
    return s_type.lower() == 'interface'


def filter_private((s_var, (s_val, s_type))):
    return s_type.lower() == 'private'


def filter_public((s_var, (s_val, s_type))):
    return s_type.lower() == 'public'


class T_CfgList(list):
    """This list class exists to permit simple filtering of its items."""

    def __init__(self, s_pathCfg='', s_nodeType=''):
        """As input, the initializer accepts a string with this syntax on each
        line:
                 type Name=Value
        where type is one of
                     public
                     private
                     interface
        Extra white space between symbols is tolerated.
        """

	global errorFlag

        # Massage the cfg-file format
        o_cfgLinesFiltered_List = []
	
	if not s_pathCfg:  return None

        try:
            o_cfgFile = open(s_pathCfg, 'r')
            s_input = o_cfgFile.readlines()
            o_cfgFile.close()

        except IOError:
            # It appears that this node does not have a cfg file
            print " chaindot.py WARNING: could not open " + s_pathCfg 
	    return None

        for s_line in s_input:
            s_line.lstrip()             # Ignore initial white space

                                        # Keep only non-comment lines
                                        # (Line-feed character is always present)
            if len(s_line) < 2 or s_line[0] == '#':
                continue

            s_line = s_line[:-1]        # Remove the line feed

            n_firstWhite = s_line.find(' ')    # Remember first white space
            #s_noWhite = s_line.replace(' ','') # Remove all non-significant white
                                        # Use ' ' and '=' to split line into 3
            #s_type=s_noWhite[0 : n_firstWhite]
	    s_type=s_line[0 : n_firstWhite]
	    
	    if not s_type.lower() in ["interface", "public", "private"]:
	        print "chaindot.py ERROR: unrecognized type "+ s_type +" in a non module config file " + s_pathCfg 
		errorFlag = True


	    if s_nodeType != "MODULE" and s_type == "interface":
	        print "chaindot.py ERROR: interface variable in a non module config file " + s_pathCfg 
		errorFlag = True
	        
            try:
                #(s_var, s_val) = s_noWhite[n_firstWhite:].split('=')
                (s_var, s_val) = s_line[n_firstWhite:].split('=')

            except Exception, E:
                print "chaindot.py ERROR:  invalid syntax in string, ", s_line
                print "                    ", E
                continue
		## sys.exit('Bad cfg file')

                                        # This syntax allows conversion to a dict
            self.append((s_var.lstrip(), (s_val, s_type)))



    def interface_vars(self):
        """Returns a list that contains only the interface variables"""
        return list(filter(filter_interface, self))

    def private_vars(self):
        """Returns a list that contains only the private variables"""
        return list(filter(filter_private, self))

    def public_vars(self):
        """Returns a list that contains only the public variables"""
        return list(filter(filter_public, self))

    def SetVars(self):
        """This is the method prints the list's contents so as to 'set' the
        variables in k-shell format."""

        str=''
        for (s_var, (s_val, s_type)) in self:
            str=str + s_var + '=' + s_val + ';\n'
        return str

    def UnsetVars(self):
        """This is the method prints the list's contents so as to 'unset' the
        variables in k-shell format."""

        str=''
        for (s_var, (s_val, s_type)) in self:
            ## NOTE:  unset returns an error if the variable does not exist
            ##str=str + 'unset ' + s_var + ';\n'
            str=str + 'if [ ${' + s_var + ':+1} ]; then unset ' + s_var + '; fi;\n'
        return str



class T_Chain:
    """This class does just one thing:  it follows down the chain of nodes,
    dotting configuration files along the way.  It simply encapsulates the
    methods that accomplish this."""

    def __init__(self, s_exptPath, s_NodePath, s_outFileName):

                                        # path to the experiment directory
        self.s_exptPath = s_exptPath
        self.s_exptName = os.path.realpath(s_exptPath).split('/')[-1]
        self.s_currentNodeDir ='..'     # string: directory of current node

                                        # list: node-path in expt to sought node
        self.o_tree_List = s_NodePath.split('/')
	self.o_tree_List=[self.s_exptName]+self.o_tree_List

        self.s_NodeName = self.o_tree_List[-1]

        self.o_privates = T_CfgList()   # List of current private variables
        self.o_publics = T_CfgList()    # List of current public variables

                                        # Digest the node sought
        if l_debug: print 's_NodePath=', s_NodePath

        #
        # Read the flow.xml
        #
        s_xmlFileName = s_exptPath + '/flow.xml'
        o_xmlFile = file(s_xmlFileName)

                                        # Read the flow.xml
                                        # (This permits identifying the modules)
        self.o_node = expatbuilder.parse(o_xmlFile).documentElement
        o_xmlFile.close()


        #
        # Open the output file, to be dotted by the client
        #
        self.s_pwd = os.getenv('PWD')
        self.o_dotout = open(s_outFileName, 'w')

        

    def DotTheChain(self):
        """To the *.dot file, write the necessary shell commands to set the
        variables."""

        #
        # Establish the starting point of the chain
        #
        self.o_dotout.write('\n# ' + 'EXPERIMENT' +' '+
                            self.o_node.getAttribute('name') + ':\n')
#experiment config
        self.__dotCfg(self.o_tree_List[0], "EXPERIMENT" )
                                        # Advance to first node name sought
        self.o_tree_List = self.o_tree_List[1:]
#first module config
        self.__dotCfg(self.o_tree_List[0], self.o_node.tagName)
                                        # Advance to first node name sought
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
                    self.o_dotout.write('\n# ' + o_child.tagName +' '+
                                                 o_child.getAttribute('name') +
                                        ':\n')

                    # Dot the configuration for this link in the chain
                    self.__dotCfg(self.o_tree_List[0], o_child.tagName)

                                        # Advance to the node just found
                    self.o_node = o_child
                                        # Advance to the next node name sought
                    self.o_tree_List = self.o_tree_List[1:]
                    break

            assert l_ChildFound, "In *.xml the child, "+ self.o_tree_List[0] + \
                                 ", not found below "+ \
                                 self.o_node.getAttribute('name')

        if l_debug: print 'sought node=', self.o_node.tagName, \
                          self.o_node.getAttribute('name')

        # Move the dot file to its final destination
        self.o_dotout.close()

    def __dotCfg(self, s_cfg, s_nodeType):
        """To dot a single configuration file in the chain, write to the *.dot
        file the necessary shell commands to set the variables.  In addition,
        track the private and interface variables and add any commands required
        by these."""

        s_nodeType = s_nodeType.upper() # Ensure upper case

        if l_debug: print "in dotCfg, s_cfg=", s_cfg, "\n", \
                          "           s_nodeType=", s_nodeType

        if (s_nodeType == 'MODULE'):    # If this is a new module
                                        # Reset the config-file path
            self.s_currentNodeDir = 'modules'


        # Construct the path to the configuration file
	
	#skip out loops if included in the node path
	if s_nodeType == 'LOOP':
            return ()

        if s_nodeType == 'TASK':        # There is no directory for a task, grab the entire config file for tasks
	    s_pathCfg = os.path.join(self.s_exptPath,
                                 self.s_currentNodeDir,
                                 s_cfg + '.cfg'
                                )
	    try:
                o_cfgFile = open(s_pathCfg, 'r')
                s_input=o_cfgFile.readlines()
                o_cfgFile.close()

	        for s_line in s_input:
                    s_line.lstrip()             # Ignore initial white space
                                                # Keep only non-comment lines
                    if len(s_line) < 2 :  ##or s_line[0] == '#':
                       continue
                    self.o_dotout.write(s_line)
		return ()

            except IOError:
               # It appears that this node does not have a cfg file
               self.o_dotout.write("# - - - >> Could not open " + s_pathCfg + "\n")
               o_cfgList = T_CfgList()
               print "ERROR: Task node must have a configuration file."
               sys.exit(1)
	else:         # not a task 
            self.s_currentNodeDir =  os.path.join(self.s_currentNodeDir, s_cfg)

        if s_nodeType == 'EXPERIMENT':
            s_pathCfg = os.path.join(self.s_exptPath, 'experiment.cfg')
	else:      #containers
	    s_pathCfg = os.path.join(self.s_exptPath,
                                 self.s_currentNodeDir,
                                 'container.cfg'
                                )
	    

                                        # For backwards compatibility:
        self.s_task_cfg = s_pathCfg     # Remember the last cfg path
 
        # Concatenate the configuration variables into a temporary list
        o_cfgList = T_CfgList(s_pathCfg,s_nodeType)


        if (s_nodeType == 'MODULE'):    # If this is a new module

                                        # Split the interface variables out of
                                        # the list
            o_interfaces = T_CfgList()
                                        # Pass backwards through the list,
                                        # because some elements will be popped
            for n_index in range(len(o_cfgList)-1, -1, -1):
                if o_cfgList[n_index][1][1].lower() == 'interface':
                    o_interfaces[0:0] = [o_cfgList.pop(n_index)]

                                        # Treat interface and private variables
            self.__StartNewModule(o_interfaces)

                                        # Add the new values into the dot file
        self.o_dotout.write(o_cfgList.SetVars())

                                        # Track new variables, according to type
        self.o_privates.extend(o_cfgList.private_vars())
        self.o_publics.extend(o_cfgList.public_vars())


    def __StartNewModule(self, o_interfaces):
        """When a new module is encountered in the dot chain, it is necessary to
             - treat any interface variables, taking their values before
               advancing to the new scope
             - advance to the new scope:
                 - remove any old private variables
                 - unhide any public variables that were hidden by the privates
             - in future, remember to treat the interface variables as privates
        """

                                        # Set any interface variables,
                                        # before erasing old private variables
        self.o_dotout.write(o_interfaces.SetVars())

                                        # Unset any old private variables
        self.o_dotout.write(self.o_privates.UnsetVars())

                                        # Create a temporary dictionary view
        o_publicsDict=dict(self.o_publics)

                                        # Unhide any public variables that were
                                        # hidden by the privates
        for (s_var, (s_val, s_type)) in self.o_privates:
            if o_publicsDict.has_key(s_var):
                self.o_dotout.write(s_var + '=' + o_publicsDict[s_var][0] +';\n')

        del self.o_privates[0:]         # Forget the old private variables

                                        # Transfer any interface variables to be
                                        # new private variables
        self.o_privates.extend(o_interfaces)
        del o_interfaces[0:]

def main():    

    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-e","--exp_path",dest="expPath",default=os.getenv('SEQ_EXP_PATH'),
                      help="Full experiment PATH (default SEQ_EXP_PATH)",metavar="PATH")
    parser.add_option("-n","--node_path",dest="nodeName",default=None,
                      help="Full PATH to the desired node (mandatory)",metavar="PATH")
    parser.add_option("-o","--output",dest="out",default=None,
                      help="Output dottable FILE containing in-scope variables (mandatory)",metavar="FILE")
    (options,args) = parser.parse_args()
    
    # Check for mandatory arguments
    if not options.nodeName:
        print "\nError: a fully-qualified node name (--node_path) is required\n"
        parser.print_help()
        sys.exit(1)
    if not options.out:
        print "\nError: an output file name (--output) is required\n"
        parser.print_help()
        sys.exit(1)
    


    MyChain = T_Chain(options.expPath, options.nodeName.lstrip("/"), options.out)
    MyChain.DotTheChain() 
    
    if errorFlag:
       sys.exit(1)

    
if __name__ == "__main__":
    main()
