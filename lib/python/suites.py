#!/usr/bin/env python
import optparse,os,sys
import xml.etree.ElementTree

class Suites(dict):
    """General Mestro suite information"""
    def __init__(self,cfgfile):
        """Class constructor"""
        try:
            self.tree = xml.etree.ElementTree.parse(cfgfile)
            self.root = self.tree.getroot()
            self.exps = [elem.text for elem in self.root.findall(".//Exp")]
        except IOError:
            sys.stderr.write("Error: cannot read from "+cfgfile+"\n")
            sys.exit(-1)

    def print_active(self):
        """Generate a list of active experiments"""
        [sys.stdout.write(exp+"\n") for exp in self.exps]

