#!/bin/ksh

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
setup_truepath=${TASK_BASEDIR}/.setup/task_setup_truepath
if [[ ${TASK_SETUP_NOEXEC:-0} > 0 ]] ; then
    printf '** skipping TASK_SETUP execution with $TASK_SETUP_NOEXEC=%s **\n' ${TASK_SETUP_NOEXEC}
    if [[ ! -f ${setup_truepath} ]] ; then
	setup_truepath=$(which true_path)
	printf '\tUnable to find true_path in %s ... will use %s\n' ${TASK_BASEDIR} ${setup_truepath}
    fi
else
    printf "** TASK_SETUP begins **\n"
    task_setup-0.9.2.py --environment ${tmpfile} ${arglist} || exit 1
    printf "** TASK_SETUP ends **\n"
fi

# Export 
rm -f ${tmpfile}
if [ -n "${TASK_BASEDIR}" ] ; then
  if [ -d ${TASK_BASEDIR}/bin ] ; then export TASK_BIN=$(${setup_truepath} ${TASK_BASEDIR}/bin) ; fi
  if [ -d ${TASK_BASEDIR}/work ] ; then export TASK_WORK=$(${setup_truepath} ${TASK_BASEDIR}/work) ; fi
  if [ -d ${TASK_BASEDIR}/input ] ; then export TASK_INPUT=$(${setup_truepath} ${TASK_BASEDIR}/input) ; fi
  if [ -d ${TASK_BASEDIR}/output ] ; then export TASK_OUTPUT=$(${setup_truepath} ${TASK_BASEDIR}/output) ; fi
fi
