from autogen.coding import CodeBlock,CodeExecutor,CodeExtractor,CodeResult

"""
On ConversableAgent, we have the following methods:
     _generate_code_execution_reply_using_executor -  highest level method that starts all this workflow and used if custom code executor is given
        first custom executor made from the user given config dict using the CodeExecutorFactory.create() method
        extracts messages to scan for code using the argument "last_n_messages" in the config dict
        uses extract_code_blocks() method from the _code_extractor property (a Class) of the custom executor to extract code blocks
        uses execute_code_blocks() method from the custom executor to execute the code blocks that returns the result in a class CodeResult

    generate_code_execution_reply - used if LocalCodeExecutor / DockerCodeExecutor is used
        uses seperate extract_code() function from code_utils.py to extract code blocks from the message
        uses execute_code_blocks() method from ConversableAgent to execute the code blocks
            execute_code_blocks() workflow:
                execute_code_blocks() -> run_code() -> execute_code() from code_utils.py

        so therefore, the lowest level method which executes the code is execute_code() from code_utils.py
            check line number 441 for an exception handling block which handles TimeoutException:
                here we can add our own logic if needed

        It uses a ThreadPoolExecutor to run the code in a separate thread. This allows for timeout management.

    we need to first override generate_reply(), so places where generate reply is used:
        

"""


