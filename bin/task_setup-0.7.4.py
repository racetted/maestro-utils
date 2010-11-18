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
    cfg.setOption(option,value) - Set the named option ('delimiter_var',
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
    delimiter  - Delimiter for keywords in the configuration file (default '::')
    verbosity  - Boolean to produce verbose output.
    cleanup    - Boolean to clean task directory before setup.
    force      - Force action despite warnings.
"""

__version__ = "0.7.0"
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
from time import gmtime, strftime


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
    if (verbose): print "Warning: unable to find "+name+" in path"
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
    delimiter_var = '::'
    delimiter_exec = '`'
    verbosity = False
    cleanup = False
    force = False

    def __init__(self,section,set=None):
        """Class constructor"""
        self.section = section
        self.set = set

    def _resolveKeywords(self,entry):
        """Resolve special keywords in the entry"""
        host = None
        updated = entry
        delim = re.compile(self.delimiter_var+'(.*?)'+self.delimiter_var)
        remote_delim = re.compile('@')
        keywords = delim.findall(entry)
        for keyword in keywords:
            elements = remote_delim.split(keyword)
            remote = (len(elements) == 2) and True or False
            env = []
            for element in elements:
                this_element = os.environ.get(element)
                if this_element:
                    env.append(this_element)                
                else:                    
                    if self.set:
                        try:
                            this_element = self.set[element]
                            env.append(this_element)
                        except KeyError:
                            print "Warning: Environment/Set variable "+element+" undefined ... ignoring"
                            env.append(element)
                    else:
                        print "Warning: Environment variable "+element+ " undefined ... ignoring"
                        env.append(element)                        
            if len(env) > 0 and env[0]:
                replacement = ''
                if remote:
                    localhost = os.environ.get('TRUE_HOST')
                    localpath = env[0]
                    if not localhost:
                        print "Warning: Unable to get ${TRUE_HOST} value ... no remote substitution"
                        replacement = localpath
                    if not replacement:
                        try:
                            remotehost = element[1]                            
                            remotehost = env[1]
                        except IndexError:
                            print "Warning: Unable to expand elements of remote path ... no remote substitution"
                    if not replacement:
                        try:                            
                            start_index = localpath.rindex('/'+localhost)       
                            host_replace = re.compile('(/)'+localhost+'(/|$)',re.M)
                            replacement = localpath[0:start_index]+host_replace.sub(r'\1'+remotehost+r'\2',localpath[start_index:])
                            host = remotehost
                        except ValueError:
                            print "Warning: Cannot find local host name "+localhost+ " in path "+localpath
                    if not replacement:
                        replacement = localpath
                else:                    
                    replacement = ''.join(env)
                updated = re.sub(self.delimiter_var+keyword+self.delimiter_var,replacement,updated)
        remote_split = remote_delim.split(updated,maxsplit=1)
        updated = remote_split[0]
        try:
            host = remote_split[1]
        except IndexError:
            pass                
        return((updated,host))

    def _executeEmbedded(self,entry):
        """Execute backtic embedded commands and substitute result"""
        have_subprocess=True
        try:
            import subprocess
        except ImportError:
            have_subprocess=False
        updated = entry
        delim = re.compile(self.delimiter_exec+'(.*?)'+self.delimiter_exec)
        commands = delim.findall(entry)
        for command in commands:
            if have_subprocess:
                p = subprocess.Popen(command,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                error_message = p.stderr.read().rstrip('\n')
                updated = delim.sub(p.stdout.read().rstrip('\n'),updated,count=1)
            else:
                (stdin,stdout,stderr) = os.popen3(command,'r')
                error_message = stderr.read().rstrip('\n')
                updated = delim.sub(stdout.read().rstrip('\n'),updated,count=1) 
                stdin.close()
                stdout.close()
                stderr.close()
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
            print "Warning: ignoring malformed configuration line: "+line
            return(False)
        lastSlash = re.compile('/$',re.M)
        (entry["link"],entry["link_host"]) = self._resolveKeywords(lastSlash.sub('',rawLink))
        entry["target_type"] = lastSlash.search(rawLink) and 'directory' or 'file'
        (entry["target"],entry["target_host"]) = self._resolveKeywords(rawTarget)        
        entry["target"] = self._executeEmbedded(entry["target"])
        if search_path:
            entry["target"] = which(entry["target"])
        entry["copy"] = False
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

    def __init__(self,file,taskdir=None,set=None):
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
        try:
            fd = open(file,"rb")
            self.configData = fd.readlines()
        except IOError:
            print "Error: unable to read from "+file
        fd.close()

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
                os.mkdir(subdir)
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

    def _upload_dir(self):
        """Set the upload directory name"""
        if not self.taskdir:
            print "Warning: 'taskdir' not set for upload directory configuration ... skipping upload check."
            return(None)
        upload = os.path.join(os.path.dirname(self.taskdir),self.taskname+"_upload")
        if (not os.path.isdir(upload)):
            return(None)
        return(upload)

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
                os.makedirs(self.taskdir)
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
                                   "target":sys.argv[0],
                                   "target_type":'file',
                                   "target_host":None,
                                   "copy":False,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        self._append_meta("setup",{"link":"task_setup.cfg",
                                   "target":self.configFile,
                                   "target_type":'file',
                                   "target_host":None,
                                   "copy":True,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        self._append_meta("setup",{"link":"task_setup_call.txt",
                                   "target":self.callFile,
                                   "target_type":'file',
                                   "target_host":None,
                                   "copy":True,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        self._append_meta("setup",{"link":"task_setup_env.txt",
                                   "target":self.envFile,
                                   "target_host":None,
                                   "target_type":'file',
                                   "copy":True,
                                   "create_target":False,
                                   "link_host":None,
                                   "link_only":False})
        if self.setFile:
            self._append_meta("setup",{"link":"task_setup_set.txt",
                                       "target":self.setFile,
                                       "target_type":'file',
                                       "target_host":None,
                                       "copy":True,
                                       "create_target":False,
                                       "link_host":None,
                                       "link_only":False})
        true_path=which('true_path',verbose=self.verbosity)
        if true_path:
            self._append_meta("setup",{"link":"task_setup_truepath",
                                       "target":true_path,
                                       "target_type":'file',
                                       "target_host":None,
                                       "copy":False,
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
            make_dir = "ssh "+entry["target_host"]+" mkdir -p "+directory
            if have_subprocess:
                p = subprocess.Popen(make_dir,shell=True,stderr=subprocess.PIPE)
                error = p.stderr.read()
            else:
                (stdin,stdout,stderr) = os.popen3(make_dir,'r')
                error = stderr.read()
            if len(error) > 0:
                print "Error: unable to create remote directory "+entry["target_host"]+':'+directory
		print "Error: attempt to connect to "+entry["target_host"]+" returned STDERR "+error
                status = self.error
        else:
            if not os.path.isdir(directory):
                try:
                    os.makedirs(directory)
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
        prefix='^\s*#[^#]+\s*'
        validLine = re.compile(prefix+'(.+)',re.M)
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
                        currentSection = head.group(1)
                        if currentSection in self.ignore_sections:
                            currentSection = None
                        else:                            
                            self["sections"][currentSection] = Section(currentSection,set=self.set)
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
        upload_dir = self._upload_dir()
        for section in self["sections"].keys():
            if (self.verbosity): print "  <"+section+">"
            if upload_dir: section_upload_dir = os.path.join(upload_dir,self._map(section))
            abs_subdir = os.path.join(self.taskdir,self._map(section))
            sub_status = self._subdir_setup(abs_subdir)
            if sub_status != self.ok: return(sub_status)
            for entry in self["sections"][section]:                
                if not entry["target"]:
                    print "Error: empty target for "+entry["link"]+" ... skipping"
                    status = self.error
                    continue
                link_only = entry["link_only"]
                src = []
                if upload_dir:
                    uploaded_path = os.path.join(section_upload_dir,entry["link"])                    
                    if os.path.exists(uploaded_path):
                        src.append(uploaded_path)
                        link_only = True  
                if (len(src) == 0): src.extend(glob.glob(entry["target"]))
                dest = os.path.join(abs_subdir,entry["link"])
                if not os.path.isdir(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))                    
                if os.path.islink(dest): os.remove(dest)
                dest_is_dir = False                
                if len(src) == 0:
                    src.append(entry["target"])                    
                elif entry["target_type"] == 'directory' and not link_only or len(src) > 1:
                    dest_is_dir = True
                    if not os.path.isdir(dest):
                        try:
                            os.makedirs(dest)
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
                    if os.path.isdir(true_src_file):
                        if entry["target_type"] != 'directory':
                            if (self.verbosity): print "Warning: "+entry["target_type"]+" link "+entry["link"]+ \
                               " refers to a directory target "+entry["target"]
                        try:
                            os.symlink(path2host(entry["target_host"],true_src_file),dest_file)
                            if (self.verbosity): print "Info: linked directory "+dest_path_short+" => "+src_file_prefix+true_src_file
                        except IOError:
                            print "Error: error creating symlink for directory "+dest_path_short+" => "+src_file_prefix+true_src_file
                            status = self.error
                    else:
                        isfile = True
                        if entry["target_host"]:
                            check_file = "ssh "+entry["target_host"]+" 'if [ -f "+true_src_file+ \
                                         " ] ; then echo 1 ; else echo 0 ; fi'"
                            if have_subprocess:
                                p = subprocess.Popen(check_file,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                                output = p.stdout.read()
                                error = p.stderr.read()
                            else:
                                (stdin,stdout,stderr) = os.popen3(check_file,'r')
                                output = stdout.read()
                                error = stderr.read()
                            if len(error) > 0:
                                print "Warning: STDERR returned from "+entry["target_host"]+" is "+error
                                isfile = False
                                status = self.error
                            elif not int(output) == 1:
                                isfile = False
				if not link_only: 
				    print "Error: required file "+true_src_file+" does not exist on host "+entry["target_host"]
				    status = self.error
                        else:
                            try:
                                fd = open(true_src_file,'r')
                            except IOError:
                                isfile = False
                        if isfile and entry["target_type"] != 'file' and len(src) == 1:
                            if (self.verbosity): print "Warning: "+entry["target_type"]+" link "+entry["link"]+ \
                               "/ refers to a file target "+entry["target"]
                        if isfile or link_only:
                            try:
                                if entry["copy"] and not link_only:
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

    print "Main started" + strftime("%H:%M:%S", gmtime())


    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-f","--file",dest="configFile",
                      help="configuration FILE name (full path)",metavar="FILE")
    parser.add_option("-d","--delimiter",dest="delimiter",default='::',
                      help="keyword DELIMITER [default ::]",metavar="DELIMITER")
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

    # Check arguments for errors
    if not options.configFile:
        print "\nError: a configuration file (--file=/path/to/config/file) must be provided\n"
        parser.print_help()
        sys.exit(1)
    if not os.path.isfile(options.configFile):
        print "Error: configuration file "+options.configFile+" does not exist"
        sys.exit(1)

    # Read, parse and act on configuration file for task setup
    cfg = Config(file=options.configFile,taskdir=options.basedir,set=options.environment)
    cfg.setOption('cleanup',options.clean)
    cfg.setOption('force',options.force)
    cfg.setOption('verbosity',options.verbose)
    cfg.setOption('delimiter_var',options.delimiter)
    cfg.getSections()
    if cfg.link():
        del cfg
	sys.exit(0)
    else:
        if cfg.verbosity: print " *** Error: problematic completion from task_setup.py *** "
        del cfg
	sys.exit(1)
