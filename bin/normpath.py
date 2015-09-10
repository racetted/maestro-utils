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

import optparse
import os.path
import sys
def main(): 

    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-p","--path",dest="path",default=None,
                      help="Returns python-normalized PATH.)",metavar="FILE")
    (options,args) = parser.parse_args()
    
    sys.stdout.write(os.path.normpath(options.path))


if __name__ == "__main__":
    main()


