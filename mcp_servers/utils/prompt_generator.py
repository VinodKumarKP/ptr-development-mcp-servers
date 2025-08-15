from typing import List, Dict


class PromptGenerator:
    @staticmethod
    def generate_prompt_for_code_analyze_and_remediations(contents, issues=True, remediated_code=False) -> str:
        """
        Generate a prompt based on user input.

        Args:
            user_input (str): The user's input text.

        Returns:
            str: The generated prompt.

        Raises:
            ValueError: If the user input is empty or contains only whitespace.
        """

        response_format = ""
        analysis_mode = """
        Please analyze the following file and identify security issues, bugs, code quality problems, and potential improvements.
        """

        if issues and not remediated_code:
            analysis_mode = f"""{analysis_mode}\n
            Focus only on finding and explaining issues without providing remediated code.
            """

            response_format = """
            Format your response as a JSON object with the following structure:
            %issueStart
            [{
              "file_path": file path,
              "issues": [
                {
                  "description": "Issue description",
                  "severity": "Critical|High|Medium|Low",
                  "remediation": "Specific remediation steps with code",
                  "context": "Additional explanation",
                  "line_number": "Line number where the issue was found"
                }
              ]
            }]
            %issueEnd
            """

        if remediated_code and not issues:
            analysis_mode = f"""{analysis_mode}\n
            Focus only on providing the fixed code with appropriate comments explaining the changes.
            """
            response_format = """
            Format your response as follows:
            %remediated_codeStart
            ****file path***
            // Complete remediated code including any helpful comments
            ================
            %remediated_codeEnd
            """

        if remediated_code and issues:
            analysis_mode = f"""{analysis_mode}\n
            For each issue found, provide a detailed explanation and show how to remediate it.
            Also provide a complete remediated version of the code that incorporates all fixes.
            """
            response_format = """
            Format your response with both sections:
            %issueStart
            [{
              "file_path": "{file_path}",
              "issues": [
                {
                  "description": "Issue description",
                  "severity": "Critical|High|Medium|Low",
                  "remediation": "Specific remediation steps with code",
                  "context": "Additional explanation"
                  "line_number": "Line number where the issue was found"
                }
              ]
            }]
            %issueEnd
            
            %remediated_codeStart
            // Complete remediated code including any helpful comments.
            Delimit each file with a line containing the file path surround by *** on both sides and
            and  ================ to indicate the end of the file
            %remediated_codeEnd
            
            If no issues are found, return an empty issues array and the original code as remediated code.
            """

        prompt = f"""
        You are a security and code quality expert analyzing files for vulnerabilities and quality issues.
        {contents}
        
        ## Analysis Mode
        {analysis_mode}
        
        ## Response Format
        {response_format}
        """
        return prompt

    @staticmethod
    def generate_prompt_for_test_case_generator(file_contents: List[Dict], coverage_level: str,
                                                include_mocks: bool) -> str:
        """Generate a prompt for test generation.

        Args:
            file_contents: List of dictionaries containing file information
            coverage_level: Level of test coverage (low, medium, high)
            include_mocks: Flag to indicate if mocks should be generated

        Returns:
            String containing the prompt
        """
        # Build content for prompt
        files_content = ""
        for file_info in file_contents:
            files_content += f"\n\nFILENAME: {file_info['file_path']}\n"
            files_content += f"TEST FRAMEWORK: {file_info['test_framework']}\n"
            files_content += f"CONTENT:\n{file_info['content']}\n"
            files_content += "=" * 40

        # Generate the prompt
        prompt = f"""
        You are an expert software developer specializing in writing high-quality unit tests.

        I will provide you with source code files from a repository, and your task is to generate 
        appropriate unit tests for each file. You should determine the correct test framework and 
        patterns based on the file extension and content.

        Coverage level: {coverage_level} (options: low, medium, high)
        Include mocks/stubs: {"Yes" if include_mocks else "No"}

        For each source file, please:
        1. Analyze the code to understand its functionality
        2. Generate appropriate unit tests using the specified test framework
        3. Include test cases for normal operation, edge cases, and error handling
        4. Follow best practices for the specific language and framework
        5. Include appropriate mocks and stubs as needed
        6. Include comments explaining the purpose of each test

        FILES TO TEST:
        {files_content}

        Please respond with the test files in a JSON format wrapped between %testFilesStart and %testFilesEnd markers as follows:

        %testFilesStart
        // Complete test code including any helpful comments
        Delimit each file with a line containing the file path surround by *** on both sides and
        and  ================ to indicate the end of the file
        %testFilesEnd

        Important guidelines:
        - Use naming conventions appropriate for each language and framework
        - For Python files, use pytest as the default framework
        - For JavaScript/TypeScript files, use Jest
        - For Java files, use JUnit
        - For other languages, use the appropriate standard unit testing framework
        - Create one test file per source file, following standard naming conventions
        - Make sure test files are properly named (e.g., test_module.py for a module.py file)
        - Include appropriate setup and teardown procedures
        - Include tests for all public methods and functions
        - For the {coverage_level} coverage level, focus on {"basic functionality only" if coverage_level == "low" else "main functionality and common edge cases" if coverage_level == "medium" else "comprehensive testing including edge cases and error conditions"}
        """

        return prompt
