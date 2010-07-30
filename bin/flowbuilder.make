$(SEQ_EXP_HOME)/flow.xml: $(SEQ_EXP_HOME)/modules/* $(SEQ_EXP_HOME)/modules/*/flow.xml
	@echo 'rebuilding flow'
	/users/dor/afsi/dor/tmp/flowbuilder.py -e $(SEQ_EXP_HOME) -o $(SEQ_EXP_HOME)/flow.xml 	

