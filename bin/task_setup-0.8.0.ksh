#!/bin/ksh

# This script dumps all variables defined in the current
# shell before wrapping a call to task_setup.py.  It should
# be executed in the current shell using `. task_setup.ksh [ARGS]`
# where all ARGS are passed directly to the task setup utility.

# Define subroutine to check for matching arguments
checkarg()
{
  arg=$1; shift
  var=$1; shift
  patterns=$*
  for pattern in ${patterns[*]}; do
    if [[ $(echo $arg | cut -c 1-${#pattern}) = $pattern ]] ; then
      eval $var=$(echo $arg | cut -c $((${#pattern}+1))-)
    fi
  done
  unset arg
  unset var
  unset patterns
  unset pattern
}

# Check command line arguments for the configuration file and task directory
arglist=$*
. o.set_array.dot argv $arglist
task_setup_cfgfile=
TASK_BASEDIR=
i=0
while [ -n "${argv[$i]}" ] ; do 
  if [[ ${argv[$i]} = "-f" || ${argv[$i]} = "--file" ]] ; then task_setup_cfgfile=${argv[$((i+1))]}; fi
  if [[ ${argv[$i]} = "-b" || ${argv[$i]} = "--base" ]] ; then TASK_BASEDIR=${argv[$((i+1))]}; fi
  checkarg ${argv[$i]} 'task_setup_cfgfile' '--file=' '-f='
  checkarg ${argv[$i]} 'TASK_BASEDIR' '--base=' '-b='
  i=$((i+1))
done
if [ -z "${task_setup_cfgfile}" ] ; then
  echo "WARNING: task_setup.ksh was unable to find a -f or --file argument"
fi
if [ ! -f "${task_setup_cfgfile}" ] ; then
  echo "WARNING: task_setup.ksh was unable to find specified configuration file "${task_setup_cfgfile}
fi

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
printf "** TASK_SETUP begins **\n"
task_setup-0.8.0.py --environment ${tmpfile} ${arglist}
printf "** TASK_SETUP ends **\n"

# Export 
rm -f ${tmpfile}
if [ -n "${TASK_BASEDIR}" ] ; then
  setup_truepath=${TASK_BASEDIR}/.setup/task_setup_truepath
  if [ -d ${TASK_BASEDIR}/bin ] ; then export TASK_BIN=$(${setup_truepath} ${TASK_BASEDIR}/bin) ; fi
  if [ -d ${TASK_BASEDIR}/work ] ; then export TASK_WORK=$(${setup_truepath} ${TASK_BASEDIR}/work) ; fi
  if [ -d ${TASK_BASEDIR}/input ] ; then export TASK_INPUT=$(${setup_truepath} ${TASK_BASEDIR}/input) ; fi
  if [ -d ${TASK_BASEDIR}/output ] ; then export TASK_OUTPUT=$(${setup_truepath} ${TASK_BASEDIR}/output) ; fi
fi
