#!/bin/ksh

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


# This script dumps all variables defined in the current
# shell before wrapping a call to task_setup.py.  It should
# be executed in the current shell using `. task_setup.ksh [ARGS]`
# where all ARGS are passed directly to the task setup utility.

# Define subroutine to check for matching arguments
checkarg()
{
  thisarg=$1; shift
  var=$1; shift
  patterns=$*
  found=0
  for pattern in ${patterns[*]}; do
    if [[ $(echo $thisarg | cut -c 1-${#pattern}) = $pattern ]] ; then
      eval $var=$(echo $thisarg | cut -c $((${#pattern}+1))-)
      found=1
    fi
  done
  unset thisarg
  unset var
  unset patterns
  unset pattern
}

# Check command line arguments for the configuration file and task directory
. o.set_array.dot argv $*
task_setup_cfgfile=
TASK_BASEDIR=
arglist=
i=0
while [ -n "${argv[$i]}" ] ; do 
  arg=${argv[$i]}
  checkarg $arg 'task_setup_cfgfile' '--file=' '-f='
  if [[ ${found} == 1 ]] ; then arg='' ; fi
  if [[ $arg == '-f' || $arg == '--file' ]] ; then task_setup_cfgfile=${argv[$i+1]} ; arg='' ; fi
  checkarg ${arg} 'TASK_BASEDIR' '--base=' '-b='
  if [[ $arg == '-b' || $arg == '--base' ]] ; then TASK_BASEDIR=${argv[$i+1]} ; fi
  arglist="${arglist} ${arg}"
  i=$((i+1))
done
if [ -z "${task_setup_cfgfile}" ] ; then
  echo "WARNING: task_setup.ksh was unable to find a -f or --file argument"
fi
if [ ! -f "${task_setup_cfgfile}" ] ; then
  echo "WARNING: task_setup.ksh was unable to find specified configuration file "${task_setup_cfgfile}
fi
arglist="${arglist} ${task_setup_cfgfile}"

# Clean up shell and dot configuration file
export TASK_BASEDIR
unset argv
unset i
if [[ -f ${task_setup_cfgfile} ]] ; then . ${task_setup_cfgfile} ; fi
unset task_setup_cfgfile

# Generate a temporary file containing all set variables
tmpfile=${TMPDIR:-/tmp}/task_setup_env$$
set >${tmpfile}

# Call task setup to generate task directory structure
if [[ ${TASK_SETUP_NOEXEC:-0} > 0 ]] ; then
    printf '** skipping TASK_SETUP execution with $TASK_SETUP_NOEXEC=%s **\n' ${TASK_SETUP_NOEXEC}
else
    printf "** TASK_SETUP begins **\n"
    task_setup.py --environment ${tmpfile} ${arglist} || exit 1
    printf "** TASK_SETUP ends **\n"
fi

# Export 
rm -f ${tmpfile}
if [ -n "${TASK_BASEDIR}" ] ; then
  setup_truepath=${TASK_BASEDIR}/.setup/task_setup_truepath
  if [[ ! -x ${setup_truepath} ]] ; then
    setup_truepath=$(which true_path)
    printf '\tUnable to find true_path in %s ... will use %s\n' ${TASK_BASEDIR} ${setup_truepath}
  fi
  if [ -d ${TASK_BASEDIR}/bin ] ; then TASK_BIN=$(${setup_truepath} ${TASK_BASEDIR}/bin); export TASK_BIN ; fi
  if [ -d ${TASK_BASEDIR}/work ] ; then TASK_WORK=$(${setup_truepath} ${TASK_BASEDIR}/work) ; export TASK_WORK; fi
  if [ -d ${TASK_BASEDIR}/input ] ; then TASK_INPUT=$(${setup_truepath} ${TASK_BASEDIR}/input) ; export TASK_INPUT; fi
  if [ -d ${TASK_BASEDIR}/output ] ; then TASK_OUTPUT=$(${setup_truepath} ${TASK_BASEDIR}/output) ; export TASK_OUTPUT; fi
fi
