#!/usr/bin/env python

#/* Part of the Maestro sequencer software package.
# * Copyright (C) 2011-2015  Canadian Meteorological Centre
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

import sys,re,shutil

# Update a configuration file
class Config(dict):
    """Configuration information to update"""

    # Class variables
    ok = 0
    error = 1

    def __init__(self,file,verbose=False):
        """Class constructor"""
        self["file"] = file
        self.verbose = verbose
        self["contents"] = self._readcfg()

    def _readcfg(self):
        """Read and parse configuration file"""
        try:
            if (self.verbose): print "Opening file "+self["file"]+" for reading"
            fd = open(self["file"],'r')
            try:
                contents = fd.readlines()
                if (self.verbose): print "Read contents of "+self["file"]
            finally:
                fd.close()
        except:
            sys.stderr.write("unable to read from "+self["file"])
            sys.exit(self.error)
        return(contents)

    def update(self,version):
        """Dispatch to update file contents to the specified version"""
        pyversion = re.sub('\.','_',version)
        update_function = getattr(self,"_update_%s" % pyversion)
        if (self.verbose): print "Updating contents to version "+version
        self["updated"] = update_function()
        if (self.verbose): print "Update complete"

    def write(self,backup):
        """Write to output file after creating a backup if necessary"""
        if (backup):
            backup_file = self["file"]+'.bak'
            shutil.copyfile(self["file"],backup_file)
            if (self.verbose): print "Backing up "+self["file"]+" to "+backup_file
        try:
            if (self.verbose): print "Opening file "+self["file"]+" for writing"
            fd = open(self["file"],'w')
            try:
                [fd.write(line) for line in self["updated"]]
            finally:
                fd.close()
        except OSError:
            sys.stderr.write("unable to open "+self["file"]+" for writing")
            sys.exit(self.error)
        
    def _update_0_9_0(self):
        """Update to task_setup 0.9.0"""
        updated = []
        for line in self["contents"]:
            upline = line
            if re.match('^\s*#',line):
                upline = re.sub(r'::(.*?)::',r'${\1}',line)     #Update keyword delimiters
                upline = re.sub(r'(\S+)@(\S+)',r'\2:\1',upline) #Update remote host syntax
            updated.append(upline)
        return(updated)
            
# Executable segment
if __name__ == "__main__":
    import optparse

    # Command line argument parsing
    usage = "%prog [options] CONFIG_FILE"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-r","--version",dest="version",default='0.9.0',
                      help="update to VERSION syntax",metavar="VERSION")
    parser.add_option("-v","--verbose",dest="verbose",action="store_true",
                      help="verbose runtime output",default=False)
    parser.add_option("-b","--backup",dest="backup",action="store_true",
                      help="create backup files (.bak)",default=False)
    (options,args) = parser.parse_args()

    # Ensure that the user has provided a configuration file
    try:
        cfgFile = args[0]
    except IndexError:
        parser.print_help()
        sys.exit(1)

    # Read, parse and act on configuration file for task setup
    cfg = Config(file=cfgFile,verbose=options.verbose)
    cfg.update(options.version)
    cfg.write(options.backup)
