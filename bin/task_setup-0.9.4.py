#!/usr/bin/env python

#-------------------------------------------------------------------
# task_setup.py
#
# Module / executable to perform task setup operations
#-------------------------------------------------------------------

"""Create and fill a task runtime directory

INTRODUCTION
This task setup utility makes use of a pair of internal classes
('Section' and 'Config') to convert information contained in a
configuration file into the complete layout of a task directory.
The primary user access to this utility is through the 'Config'
class.

CONFIG CLASS

  METHODS
    cfg = Config('/path/to/config/file.cfg') - Class constructor.  This
         method reads and caches the contents of the named input
         configuration file.  The output from this method is a instance
         of the Config class.
    cfg.getSections() - Parse the sections of the configuration file
         to generate a list of 'links', 'targets' and 'options'.  These
         values are stored internally by the instance.
    cfg.link() - Generate the subdirectories and links to the files
         identified in the config file.
    cfg.setOption(option,value) - Set the named option ('delimiter_exec',
         'verbosity','cleanup','force') to the value specified in the argument.
         This method should be called before the 'getSections' method
         to ensure that keywords are properly resolved.

  CLASS VARIABLES
    configData - Cached copy of the data read from the configuration file.
    configFile - Name of the configuration file.
    taskdir    - User-specified (not true-path'd) path to task directory.
    basepath   - True path to working directory below task level.
    taskname   - Task name.
    subdir_sectionMap - Name mapping from configuration file sections to
         task subdirectories.
    verbosity  - Boolean to produce verbose output.
    cleanup    - Boolean to clean task directory before setup.
    force      - Boolean to force actions despite warnings.
    error      - Error code for return.
    ok         - Successful completion code for return.

SECTION CLASS

  METHODS
    s = Section(section) - Class constructor.  This method returns an
         instance of the 'Section' class for the particular section
         identified in the argument list.
    s.add(line) - Add the contents of a configuration file line to
         this this instance of the Section class.  This information
         will be appended to any existing additions made to the instance.

  CLASS VARIABLES
    delimiter_exec  - Delimiter for embedded commands (default '`')
    verbosity       - Boolean to produce verbose output.
    cleanup         - Boolean to clean task directory before setup.
    force           - Force action despite warnings.
"""

__version__ = "0.9.4"
__author__  = "Ron McTaggart-Cowan (ron.mctaggart-cowan@ec.gc.ca)"

#---------
# Imports
#---------
import os
import sys
import shutil
import re
import optparse
import tempfile
import types

def mkdir_p(path):
    import os,sys,errno
    try:
        os.makedirs(path)
    except OSError:
        value = sys.exc_info()[1][0]
        if value == errno.EEXIST:
            pass
        else:
            sys.stderr.write('task_setup.py::os.makdeirs() returned the following error information on an attempt to create ' \
                             +path+': '+str(sys.exc_info())+"\n")
            raise

def which(name,verbose=True):
    """Duplicates the functionality of UNIX 'which' command"""    
    if re.search('/',name):
        return(name)
    for dir in re.split(':',os.environ['PATH']):
        fullname=os.path.join(dir,name)
        try:
            if os.path.isfile(fullname):
                if os.access(fullname,os.X_OK): return(fullname) 
        except:
            continue
    if (verbose): print "Warning: unable to find "+name+" in path \nPATH="+os.environ['PATH']
    return('')  

def path2host(machine,path):
    """Convert a machine/abspath pair to the heirarchical part of a URI"""
    if machine:
        return(machine+':'+path)
    else:
        return(path)

class Section(list):
    """Data and functions applicable to individual configuration sections"""

    # Class variables
    delimiter_exec = '`'
    verbosity = False
    cleanup = False
    force = False

    def __init__(self,section,set=None,cfg=None):
        """Class constructor"""
        self.section = section
        self.set = set
        self.cfg = cfg

    def _resolveKeywords(self,entry):
        """Resolve special keywords in the entry (no procesing for keywords in embedded commands)"""
        delim_start='\$\{'
        delim_end='}'
        delim = re.compile(delim_start+'(.*?)'+delim_end)
        dollar = re.compile('\$')
        elements = re.split(self.delimiter_exec+'(.*?)'+self.delimiter_exec,entry)
        for i in range(0,len(elements)):
            if i%2:
                # This is an embedded command.  Add delimiters and do not substitute keywords.
                elements[i] = self.delimiter_exec+elements[i]+self.delimiter_exec
            else:
                # This is a standard string.  Attempt to replace all keywords.
                keywords = delim.findall(elements[i])
                for keyword in keywords:
                    if not keyword: continue
                    this_keyword = os.environ.get(keyword)
                    if not this_keyword:
                        if self.set:
                            vartype = 'unknown'
                            try:
                                this_keyword = self.set[keyword]
                            except KeyError:
                                vartype = 'environment/set'
                        else:
                            vartype = 'environment'
                        if not this_keyword:
                            warnline = "Error: "+vartype+" variable "+keyword+" undefined ... empty substitution performed"
                            sys.stderr.write(warnline+'\n')
                            if (self.verbosity): print warnline
                            this_keyword = ''
                    elements[i] = re.sub(delim_start+keyword+delim_end,this_keyword,elements[i])
                if i == 0:
                    # Check the first entry for a host name
                    try:
                        (host,path) = re.split(':',elements[i])
                        elements[i] = path
                    except ValueError:
                        host = None
                if dollar.search(elements[i]):
                    highlight = dollar.sub(' >>> $ <<< ',elements[i])
                    elements[i] = dollar.sub(' [INVALID KEYWORD] ',elements[i])
                    warnline = "Error: keyword syntax should be ${...}, but found an unmatched $ at entry "+highlight
                    sys.stderr.write(warnline+'\n')
                    if (self.verbosity): print warnline
        updated = ''.join(elements) 
        return((updated,host))

    def _executeEmbedded(self,entry):
        """Execute backtic embedded commands and substitute result"""
        have_subprocess=True
        try:
            import subprocess
        except ImportError:
            have_subprocess=False
        updated = [entry]
        delim = re.compile(self.delimiter_exec+'(.*?)'+self.delimiter_exec)
        commands = delim.finditer(entry)
        for command in commands:
            command_prefix = (self.cfg) and '. '+self.cfg+' >/dev/null 2>&1; ' or ''
            if have_subprocess:
                p = subprocess.Popen(command_prefix+command.group(1),shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                error_message = p.stderr.read().rstrip('\n')
                outbuf = p.stdout.read().rstrip('\n')
            else:
                (stdin,stdout,stderr) = os.popen3(command_prefix+command.group(1),'r')
                error_message = stderr.read().rstrip('\n')
                outbuf = stdout.read().rstrip('\n')
                stdin.close()
                stdout.close()
                stderr.close()
            elements = re.split('\n',outbuf)
            target_list = []
            for j in range(0,len(updated)):
                for i in range(0,len(elements)):
                    target_list.append(command.re.sub(elements[i],updated[j],count=1))
            updated = target_list
            if error_message:
                print "Warning: the embedded command "+self.delimiter_exec+command+self.delimiter_exec+ \
                      " in the configuration file returned an error: "+error_message       
        return(updated)

    def add(self,line,search_path):
        """Add data to the section"""        
        data = re.split('\s+',re.sub('^(#)+',' ',line))
        entry = {}
        try:
            rawLink = data[1]
            rawTarget = ' '.join(data[2:]).rstrip()
        except IndexError:
            warnline = "Warning: ignoring malformed configuration line: "+line
            sys.stderr.write(warnline)
            if (self.verbosity): print(warnline)
            return(False)
        lastSlash = re.compile('/$',re.M)
        (link,link_host) = self._resolveKeywords(lastSlash.sub('',rawLink))
        (target,target_host) = self._resolveKeywords(rawTarget)        
        if re.match('^\s*\'*<no\svalue>',target):
            print "Info: will not create link for "+link+" because of special target value "+target
            return(False)
        entry["link_host"] = link_host
        entry["link"] = link
        entry["target_host"] = target_host
        entry["target_type"] = lastSlash.search(rawLink) and 'directory' or 'file'
        entry["target"] = self._executeEmbedded(target)
        if search_path:
            entry["target"] = [which(target) for target in entry["target"]]
        entry["copy"] = False
        entry["cleanup"] = False
        entry["create_target"] = False
        entry["link_only"] = False
        if self.section == 'output':
            entry["create_target"] = True
            entry["link_only"] = True
        self.append(entry)

class Config(dict):
    """Data and functions applicable to the task setup"""

    # Class variables
    configData = {}
    configFile = None
    taskdir = None
    basepath = None
    taskname = None
    verbosity = False
    cleanup = False
    force = False
    error = 0
    ok = 1
    subdir_sectionMap = {'input':       'input',
                         'executables': 'bin',
                         'work':        'work',
                         'output':      'output',
                         'setup':       '.setup'}  #Tags in config files (keys) are mapped to these subdir names (values)
    force_sections = ['work','setup']              #Force the creation of these sections regardless of config file contents
    search_path_sections = ['executables','setup'] #These sections will search the PATH for non-fully-qualified targets
    ignore_sections = ['seq_scheduler']            #Ignore these sections in the configuration file

    def __init__(self,file=None,taskdir=None,set=None):
        """Class constructor"""
        self.configFile = file
        self.taskdir = taskdir
        self.setFile = set
        self.set = None
        self.callFile = self._createTmpFile(sys.argv)
        self.envFile = self._createTmpFile(os.environ)
        self["file"] = file
        if set:
            self._readSetFile(set) 
        if not self.configData:
            self._readConfigFile(self["file"])

    def __del__(self):
        """Class destructor"""
        os.unlink(self.callFile)
        os.unlink(self.envFile)

    def _createTmpFile(self,contents):
        """Create and fill a temporary file, returning the file name"""
        try:
            (fdunit,filename) = tempfile.mkstemp()
            fd = os.fdopen(fdunit,"w+b")
        except OSError:
            print "Warning: Unable to create temporary file for call statement"
            return(None)        
        if type(contents) == types.InstanceType:
            keys = contents.keys()
            keys.sort()
            for key in keys:
                fd.write(str(key)+'='+str(contents[key])+'\n')
        elif type(contents) == types.ListType:
            fd.write(' '.join(contents)+'\n')
        else:
            fd.write(str(contents)+'\n')
        fd.close()
        return(filename)

    def _readSetFile(self,file):
        """Read set file"""
        try:
            fd = open(file,"rb")
            setData = fd.readlines()
        except IOError:
            print "Warning: unable to read set from "+file
            self.set = None
            return()
        fd.close()
        sep = re.compile("'")
        equal = re.compile("=")
        quote_count = 0
        self.set = {}; concat_line = ''
        for line in setData:
            quote_count += len(re.findall(sep,line))
            if quote_count%2 == 0:
                concat_line += line
                try:
                    (key,value) = equal.split(concat_line,maxsplit=1)
                except ValueError:
                    continue
                self.set[key] = value.rstrip('\n')
                concat_line = ''
            else:
                concat_line += line

    def _readConfigFile(self,file):
        """Read configuration file"""
        if not file:
            self.configData = ''
            return
        try:
            fd = open(file,"rb")
            try:
                self.configData = fd.readlines()
            finally:
                fd.close()
        except IOError:
            warnline = "Warning: unable to read from configuration file "+file
            sys.stderr.write(warnline+'\n')
            if (self.verbosity): print warnline
            self.configData = []
            self.configFile = '/dev/null'

    def _map(self,section):
        """Map a section name to a task subdirectory name"""
        try:
            subdir = self.subdir_sectionMap[section]
        except KeyError:
            print "Warning: unknown section "+section+" encountered ... no mapping done"
            return(section)
        return(subdir)

    def _subdir_setup(self,subdir):
        """Set up the requested subdirectory for the task"""
        status = self.ok
        if not os.path.isdir(subdir):
            if (self.verbosity): print "Info: creating subdirectory "+subdir
            try:
                mkdir_p(subdir)
            except OSError:
                print "Error: could not create "+subdir
                status = self.error
        return(status)

    def _get_subdirs(self,dir,absolute=True):
        """Return a list of relative or absolute expected subdirectories"""
        subdirs = [self._map(section) for section in self["sections"].keys()]
        subdirs.sort()
        if absolute:
            return([os.path.join(dir,subdir) for subdir in subdirs])
        else:
            return(subdirs)

    def _taskdir_setup(self):
        """Set up task base directory"""
        status = self.ok
        if self.cleanup:
            if os.path.isdir(self.taskdir):
                contents = [entry for entry in os.listdir(self.taskdir) if os.path.isdir(os.path.join(self.taskdir,entry))]
                if len(contents) > 0:
                    if self.force:
                        for sub in contents:
                            try:
                                shutil.rmtree(os.path.join(self.taskdir,sub))
                            except:
                                print "Error: unable to force clean workspace subdirectory "+sub
                                return(self.error)
                    else:
                        contents.sort()
                        if contents == self._get_subdirs(self.taskdir,absolute=False):
                            for sub in self._get_subdirs(self.taskdir,absolute=True):
                                try:                                
                                    shutil.rmtree(sub)
                                except:
                                    print "Error: unable to remove task subdirectory "+sub
                                    return(self.error)
                        else:
                            print "Error: Invalid and/or changed subdirectory <-> section mapping in task_setup.py."
                            print "   The requested task base directory "+self.taskdir+" contains a subdirectory that"
                            print "   is not recognized based on the configuration file "+self["file"]+"  If"
                            print "   this is a valid task base directory, please remove it manually and relaunch."
                            print "       Task subdirectories: "+str(contents)
                            print "       Mapped config sections: "+str(self._get_subdirs(self.taskdir,absolute=False))
                            return(self.error)
        if not os.path.isdir(self.taskdir):
            try:
                mkdir_p(self.taskdir)
            except OSError:
                print "Error: could not create task base directory "+self.taskdir
                return(self.error)
        elif not os.access(self.taskdir,os.W_OK):
            print "Error: task directory "+self.taskdir+" is not writeable ... exiting"
            return(self.error)
        # Set task name and working path (needs to exist for `true_path` so it can't be done during construction)
        basedir = self._getTruePath(self.taskdir)
        self.basepath = os.path.dirname(basedir)
        self.taskname = os.path.basename(basedir)
        return(status)

    def _append_meta(self,section,meta):
        """Append metadata to the specified section"""
        status = self.ok
        try:
            self["sections"][section].append(meta)
        except KeyError:
            status = self.error
        return(status)

    def _special_appends(self):
        """Add special values to sections"""
        self._append_meta("setup",{"link":"task_setup",
                                   "target":[sys.argv[0]],
                                   "target_type":'file',
                                   "target_host":None,
                                   "copy":False,
                                   "cleanup":False,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        if self["file"]:
            self._append_meta("setup",{"link":"task_setup.cfg",
                                       "target":[self.configFile],
                                       "target_type":'file',
                                       "target_host":None,
                                       "copy":True,
                                       "cleanup":False,
                                       "create_target":False,
                                       "link_host":None,
                                       "link_only":False})
        self._append_meta("setup",{"link":"task_setup_call.txt",
                                   "target":[self.callFile],
                                   "target_type":'file',
                                   "target_host":None,
                                   "copy":True,
                                   "cleanup":False,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        self._append_meta("setup",{"link":"task_setup_env.txt",
                                   "target":[self.envFile],
                                   "target_host":None,
                                   "target_type":'file',
                                   "copy":True,
                                   "cleanup":False,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        if self.setFile:
            self._append_meta("setup",{"link":"task_setup_set.txt",
                                       "target":[self.setFile],
                                       "target_type":'file',
                                       "target_host":None,
                                       "copy":True,
                                       "cleanup":True,
                                       "create_target":False,
                                       "link_host":None,
                                       "link_only":False})
        true_path=which('true_path',verbose=self.verbosity)
        if true_path:
            self._append_meta("setup",{"link":"task_setup_truepath",
                                       "target":[true_path],
                                       "target_type":'file',
                                       "target_host":None,
                                       "copy":False,
                                       "cleanup":False,
                                       "create_target":False,
                                       "link_host":None,
                                       "link_only":False})
        return(self.ok) 

    def _createTarget(self,entry,path):
        """Create target directory"""
        have_subprocess=True
        try:
            import subprocess
        except ImportError:
            have_subprocess=False     
        status = self.ok
        if not entry["create_target"]: return(status)
        directory = (entry["target_type"] == 'directory') and path or os.path.split(path)[0]        
        if entry["target_host"]:
            make_dir = "echo \"s.mkdir_onebyone "+directory+"; if [[ -d "+directory+ \
                       " ]] ; then echo TASK_SETUP_SUCCESS ; else echo TASK_SETUP_FAILURE ; fi\" | ssh "+ \
                       entry["target_host"]+" bash --login"
            if have_subprocess:
                p = subprocess.Popen(make_dir,shell=True,stderr=subprocess.PIPE,stdout=subprocess.PIPE)
                error = p.stderr.read()
                output = p.stdout.read()
            else:
                (stdin,stdout,stderr) = os.popen3(make_dir,'r')
                error = stderr.read()
                output = stdout.read()
            if not re.search("TASK_SETUP_SUCCESS",output):
                status = self.error
                if re.search("TASK_SETUP_FAILURE",output):
                    print "Error: login to "+entry["target_host"]+" successful but "+directory+" not created"
                else:
                    print "Error: unable to obtain directory status on "+entry["target_host"]
            if len(error) > 0:
                sys.stderr.write("task_setup.py::_createTarget() attempt to connect to "+entry["target_host"]+" returned STDERR "+error+"\n")
        else:
            if not os.path.isdir(directory):
                try:
                    mkdir_p(directory)
                    if (self.verbosity): print "Info: created directory "+directory+" to complete target request"
                except:
                    print "Error: unable to create "+directory+" to complete target request"
                    status = self.error
        return(status)

    def _getTruePath(self,node):
        """Get the true path of a file/directory"""
        have_subprocess=True
        try:
            import subprocess
        except ImportError:
            have_subprocess=False            
        try:
            get_true_path = "true_path "+node
            if have_subprocess:
                p = subprocess.Popen(get_true_path,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                true_src = p.stdout.read()                
            else:
                (stdin,stdout_stderr) = os.popen4(get_true_path,'r')
                true_src = stdout_stderr.read()
                stdin.close()
                stdout_stderr.close()
            if true_src == '(null)' or not true_src or re.search('No such file or directory$',true_src,re.M) or \
                   re.search('Probleme avec le path',true_src):
                true_src = node
        except OSError:
            if (os.path.exists(node)):
                print "Error: true_path does not exist or returned an error for "+src_file
                status = self.error
            true_src = node            
        return(true_src) 

    def setOption(self,option,value):
        """Option handling dispatcher"""
        try:            
            getattr(Section,option)
        except AttributeError:
            print "Error: attempt to change invalid setting "+option
            return (self.error)
        setattr(Section,option,value)
        setattr(self,option,value)
        return(self.ok)

    def getSections(self):
        """Break input data into individual sections"""
        currentSection = None
        prefix='^\s*#\s*'
        validLine = re.compile(prefix+'[^#](.+)',re.M)
        sectionHead = re.compile(prefix+'<([^/].*)>',re.M)
        sectionFoot = re.compile(prefix+'</(.*)>',re.M)
        self["sections"] = {}
        for raw_line in self.configData:
            line = re.sub('^\s+','',raw_line,re.M)
            head = False
            valid = validLine.search(line)
            if (valid):
                foot = sectionFoot.search(line)
                if foot and currentSection:
                    if foot.group(1) != currentSection:
                        print "Warning: section head <"+currentSection+"> does not match the section foot </"+foot.group(1)+"> in "+self["file"]
                    currentSection = None
                else:
                    head = sectionHead.search(line)
                    if head:
                        if currentSection:
                            print "Error: found header for "+head.group(1)+" while still in open section for "+currentSection
                            print "  Perhaps the configuration file "+self["file"]+" is missing an </"+currentSection+"> end section tag?"
                            sys.stderr.write("task_setup.py::getSections() failed parsing "+self["file"]+" at <"+head.group(1)+">\n")
                            self["sections"] = {}
                            return(self.error)
                        currentSection = head.group(1)
                        if currentSection in self.ignore_sections:
                            currentSection = None
                        else:
                            self["sections"][currentSection] = Section(currentSection,set=self.set,cfg=self["file"])
                if (currentSection and not head):                    
                    self["sections"][currentSection].add(line,currentSection in self.search_path_sections)
        for force in self.force_sections:
            self["sections"][force] = Section(force)
        self._special_appends()
        return(self.ok)
    
    def link(self):
        """Perform subdirectory creation and linking operations"""
        import glob
        have_subprocess=True
        try:
            import subprocess
        except ImportError:
            have_subprocess=False
        status = self.ok
        sub_status = self._taskdir_setup()
        if sub_status != self.ok: return(sub_status)
        for section in self["sections"].keys():
            if (self.verbosity): print "  <"+section+">"
            abs_subdir = os.path.join(self.taskdir,self._map(section))
            sub_status = self._subdir_setup(abs_subdir)
            if sub_status != self.ok: return(sub_status)
            for entry in self["sections"][section]:
                if len(entry["target"]) == 0:
                    print "Error: empty target for "+entry["link"]+" ... skipping"
                    status = self.error
                    continue
                link_only = entry["link_only"]
                src = []                
                for target in entry["target"]:
                    src.extend(glob.glob(target))                    
                dest = os.path.join(abs_subdir,entry["link"])
                if not os.path.isdir(os.path.dirname(dest)):
                    mkdir_p(os.path.dirname(dest))                    
                if os.path.islink(dest): os.remove(dest)
                dest_is_dir = False                
                if len(src) == 0:
                    src.extend(entry["target"])                    
                elif entry["target_type"] == 'directory' and not link_only or len(src) > 1:
                    dest_is_dir = True
                    if not os.path.isdir(dest):
                        try:
                            mkdir_p(dest)
                        except OSError:
                            print "Error: could not create "+section+" subdirectory "+dest
                            dest_is_dir = False
                            status = self.error
                for src_file in src:
                    if dest_is_dir and not link_only:
                        dest_file = os.path.join(dest,os.path.basename(src_file))
                    else:
                        dest_file = dest
                    dest_path_short = os.path.join(self._map(section),os.path.basename(dest_file))
                    src_file_prefix = entry["target_host"] and entry["target_host"]+':' or ''
                    true_src_file = self._getTruePath(src_file)

                    # Retreive information about remote source file
                    remote_file_type = ''
                    if entry["target_host"]:
                        check_file = "ssh "+entry["target_host"]+" 'if [[ -d "+true_src_file+ \
                                     " ]] ; then echo 2 ; elif [[ -f "+true_src_file+ \
                                     " ]] ; then echo 1 ; else echo 0 ; fi'"
                        if have_subprocess:
                            p = subprocess.Popen(check_file,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                            output = p.stdout.read()
                            error = p.stderr.read()
                        else:
                            (stdin,stdout,stderr) = os.popen3(check_file,'r')
                            output = stdout.read()
                            error = stderr.read()
                        if len(error) > 0:
                            warnline = "Warning: STDERR returned from "+entry["target_host"]+" is "+error
                            sys.stderr.write(warnline+'\n')
                            if (self.verbosity): print warnline
                            status = self.error
                        elif int(output) == 1:
                            remote_file_type = 'file'
                        elif int(output) == 2:
                            remote_file_type = 'directory'
                        else:
                            if not link_only:
                                print "Error: required file "+true_src_file+" does not exist on host "+entry["target_host"]
                                status = self.error

                    # Take care of creating directory links
                    if os.path.isdir(true_src_file) or remote_file_type is 'directory':
                        if entry["target_type"] != 'directory':
                            if (self.verbosity): print "Warning: "+entry["target_type"]+" link "+entry["link"]+ \
                               " refers to a directory target "+str(entry["target"])
                        try:
                            os.symlink(path2host(entry["target_host"],true_src_file),dest_file)
                            if (self.verbosity): print "Info: linked directory "+dest_path_short+" => "+src_file_prefix+true_src_file
                        except IOError:
                            print "Error: error creating symlink for directory "+dest_path_short+" => "+src_file_prefix+true_src_file
                            status = self.error

                    # Take care of creating file links or copies
                    else:
                        isfile = True
                        if remote_file_type is not 'file':
                            try:
                                fd = open(true_src_file,'r')
                            except IOError:
                                isfile = False
                        if isfile and entry["target_type"] != 'file' and len(src) == 1:
                            if (self.verbosity): print "Warning: "+entry["target_type"]+" link "+entry["link"]+ \
                               "/ refers to a file target "+str(entry["target"])
                        if isfile or link_only:
                            try:
                                if entry["copy"] and not link_only:                                    
                                    if entry["cleanup"]:
                                        shutil.move(true_src_file,dest_file)
                                        link_type = "moved"
                                    else:
                                        shutil.copyfile(true_src_file,dest_file)
                                        link_type = "copied"
                                else:
                                    if entry["create_target"]:
                                        status_create = self._createTarget(entry,true_src_file)
                                        if status == self.ok: status = status_create
                                        true_src_file = self._getTruePath(true_src_file)
                                    if os.path.islink(dest_file):
                                        print "Warning: overwriting existing link to "+dest_file+" with "+src_file_prefix+true_src_file
                                        os.remove(dest_file)
                                    os.symlink(path2host(entry["target_host"],true_src_file),dest_file)
                                    link_type = "linked"
                                if (self.verbosity): print "Info: "+link_type+" file "+dest_path_short+" => "+src_file_prefix+true_src_file
                            except OSError:
                                print "Error: error creating symlink for file "+dest_path_short+" => "+src_file_prefix+true_src_file
                                status = self.error
                        else:
                            print "Error: unable to link "+dest_path_short+" => "+src_file_prefix+true_src_file+" ... source file is unavailable"
                            status = self.error
            print "  </"+section+">"
        return(status)

# Executable segment
if __name__ == "__main__":

    # Command line argument parsing
    usage = "%prog [options] CONFIG_FILE"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b","--base",dest="basedir",default='.',
                      help="task base DIRECTORY",metavar="DIRECTORY")
    parser.add_option("-v","--verbose",dest="verbose",action="store_true",
                      help="verbose runtime output",default=False)
    parser.add_option("-c","--clean",dest="clean",action="store_true",
                      help="clean task directory before setup",default=False)
    parser.add_option("-r","--force",dest="force",action="store_true",
                      help="force action (ignore warnings)",default=False)
    parser.add_option("-e","--environment",dest="environment",default=None,
                      help="text FILE containing the environment in which to run",metavar="FILE")
    (options,args) = parser.parse_args()

    # Ensure that the user has provided a configuration file
    try:
        cfgFile = args[0]
    except IndexError:
        cfgFile = None

    # Read, parse and act on configuration file for task setup
    cfg = Config(file=cfgFile,taskdir=options.basedir,set=options.environment)
    cfg.setOption('cleanup',options.clean)
    cfg.setOption('force',options.force)
    cfg.setOption('verbosity',options.verbose)
    if cfg.getSections():
        pass
    else:
        if cfg.verbosity: print " *** Error: task_setup.py unable to continue *** "
        sys.exit(1)
    if cfg.link():
        del cfg
	sys.exit(0)
    else:
        if cfg.verbosity: print " *** Error: problematic completion from task_setup.py *** "
        del cfg
	sys.exit(1)
