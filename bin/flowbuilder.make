$(SEQ_EXP_HOME)/flow.xml: $(SEQ_EXP_HOME)/modules/* $(SEQ_EXP_HOME)/modules/*/flow.xml
	@echo 'rebuilding flow'
	$(SEQ_UTILS_BIN)/flowbuilder.py -e $(SEQ_EXP_HOME) -o $(SEQ_EXP_HOME)/flow.xml 	

