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

import sys
import re
import optparse

def main(): 

    # Command line argument parsing
    parser = optparse.OptionParser()
    parser.add_option("-i","--input_file",dest="inputFile",default=None,
                      help="Input FILE to replace non-quoted semi-colons for newlines)",metavar="FILE")
    (options,args) = parser.parse_args()
    
    remainderString=""
    openFile = open(options.inputFile, 'r')
    s_input=openFile.readlines()
    openFile.close()

    normalsearch=re.compile(";")
    doubleexp=re.compile("\"")
    singleexp=re.compile("\'")

    for s_line in s_input:
        s_line = s_line.rstrip()
        
        # skip empty lines
        if s_line == "":  
            print("")
            continue

        if remainderString != "":
            #print("Found remainder string, combining lines:\n" + remainderString + '\n' + "and \n" + s_line)
            s_line=remainderString + s_line + "\n"
            remainderString="" 
        if s_line != "" and s_line[-1] == '\\' and countSlashesBefore(s_line, len(s_line)-1) % 2 == 0: 
            #print("Found valid trailing slash, combining lines.") 
            remainderString=remainderString+s_line[:-1]
            continue

        matches=normalsearch.finditer(s_line)
        # sys.stderr.write("line:"+s_line)
        validDoublesList=checkValidity(s_line, doubleexp.finditer(s_line))
        validSinglesList=checkValidity(s_line, singleexp.finditer(s_line))
        ignoredSinglesList=isSingleIgnored(validDoublesList, validSinglesList)
        for ignoredSingle in ignoredSinglesList:
            validSinglesList.remove(ignoredSingle)

        for match in matches:
             if not insideQuotes(match.start(), validSinglesList, validDoublesList): 
                 s_line=s_line[0:match.start()]+'\n'+s_line[match.start()+1:]

        print(s_line)
 

def countSlashesBefore(string, position):
    count=0
    while (position-1-count >= 0 and string[position-1-count] == '\\'):
        count=count+1
    return count

def checkValidity(line, matches): 
 
    returnList=[]
    for match in matches:
        if countSlashesBefore(line, match.start()) % 2 == 0: 
            returnList.append(match.start()) 
    return returnList

def isSingleIgnored(doublesList, singlesList): 
    returnList=[]
    counter=0
    prevPos=0
    for single in singlesList:
        for double in doublesList: 
            counter+=1    
            if (counter%2 == 0):
                if (single > prevPos and single < double and prevPos > 0): 
                    returnList.append(single);
            else:
                prevPos=double
    return returnList 

def insideQuotes(position, singlesList, doublesList):
       
    counter=0
    prevPos=0

    for listItem in singlesList:
        counter+=1 
        if (counter%2 == 0):
            if (position > prevPos and position < listItem and prevPos > 0): 
                return True
        else:
            prevPos=listItem

    counter=0
    prevPos=0

    for listItem in doublesList:
        counter+=1 
        if (counter%2 == 0):
            if (position > prevPos and position < listItem and prevPos > 0): 
                return True
        else:
            prevPos=listItem
    return False 


if __name__ == "__main__":
    main()

