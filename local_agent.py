# local_agent.py - A simple agentic framework for Ollama models with robust tool-calling
 
import requests
import json
import subprocess
import os
OLLAMA_API_BASE = "http://localhost:11434/v1"
# Use the recommended model
MODEL_NAME = "Gemma-4-12B-Coder-32k:latest"
 
 # --- TOOL DEFINITIONS ---
 
def read_file_tool(path: str) -> str:
     """Read the content of a text file at the provided absolute path.
     Returns the file content or an error message.
     """
     try:
         with open(path, 'r', encoding='utf-8') as f:
             content = f.read()
         return f"File content of '{path}':\n```\n{content}\n```"
     except FileNotFoundError:
         return f"ERROR: File not found at '{path}'."
     except Exception as e:
         return f"ERROR reading file '{path}': {e}"
 
def write_file_tool(path: str, content: str) -> str:
     """Write content to a file at the provided absolute path.
     Overwrites the file if it exists. Creates it if it doesn't.
     Returns a success message or an error.
     """
     try:
         os.makedirs(os.path.dirname(path), exist_ok=True)
         with open(path, 'w', encoding='utf-8') as f:
             f.write(content)
         return f"SUCCESS: Content written to '{path}'."
     except Exception as e:
         return f"ERROR writing to file '{path}': {e}"
 
def run_command_tool(command: str) -> str:
     """Run a non-interactive shell command in a Windows environment.
     Captures and returns stdout and stderr.
     Example: `run_command_tool("dir /s d:\\AI\\Projects\\command_center")`
     """
     try:
         # Use PowerShell for robust command execution
         process = subprocess.run(
             ["powershell.exe", "-Command", command],
             capture_output=True,
             text=True,
             encoding='utf-8',
             check=True,
             timeout=300 # 5 minute timeout
         )
         output = f"STDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
         return output
     except subprocess.CalledProcessError as e:
         return f"ERROR: Command exited with code {e.returncode}:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
     except subprocess.TimeoutExpired:
         return "ERROR: Command timed out after 300 seconds."
     except Exception as e:
         return f"ERROR running command '{command}': {e}"
 
def ask_user_tool(question: str, options: list[str]) -> str:
     """Asks the user a multiple-choice question and returns their chosen option.
     Provides options as a comma-separated string to the user.
     """
     print(f"\nAGENT QUESTION: {question}")
     for i, option in enumerate(options):
         print(f"  {i+1}. {option}")
     
     while True:
         try:
             choice = input(f"Enter your choice (1-{len(options)}): ")
             choice_idx = int(choice) - 1
             if 0 <= choice_idx < len(options):
                 return options[choice_idx]
             else:
                 print("Invalid choice. Please try again.")
         except ValueError:
             print("Invalid input. Please enter a number.")
 
 # Map tool names to their functions
AVAILABLE_TOOLS = {
     "read_file": read_file_tool,
     "write_file": write_file_tool,
     "run_command": run_command_tool,
     "ask_user": ask_user_tool,
 }
 
 # --- OLLAMA INTERACTION ---
 
 # A system message that defines the agent's persona and available tools
SYSTEM_PROMPT = """
 You are an AI coding assistant named Cline. Your primary goal is to assist users with various coding tasks.
 You have access to the following tools:
 {}
 
 To use a tool, respond with a JSON object like this inside a triple backtick block:
 ```json
 {{
   "tool": "tool_name",
   "parameters": {
     "param1": "value1",
     "param2": "value2"
   }
 }}
 ```
 After a tool is executed, its output will be provided to you.
 If you need to ask the user a question, always use the `ask_user` tool with clear options.
 If you are done and have a final answer or completed the task, respond with just the answer text.
 Avoid assumptions. If you need more information, ask using the `ask_user` tool or `read_file`.
 """.format(json.dumps([
     {"name": "read_file", "description": "Reads the entire content of a text file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
     {"name": "write_file", "description": "Writes content to a file, overwriting if it exists.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
     {"name": "run_command", "description": "Runs a non-interactive shell command in a Windows environment.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}},
     {"name": "ask_user", "description": "Asks the user a multiple-choice question and returns their chosen option.", "parameters": {"type": "object", "properties": {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}}}},
 ], indent=2))
 
def chat_with_ollama(messages: list) -> dict:
     """Sends messages to Ollama and returns the response."""
     headers = {"Content-Type": "application/json"}
     payload = {
         "model": MODEL_NAME,
         "messages": messages,
         "temperature": 0.3,
         "keep_alive": "0s" # Don't keep model in VRAM after response
     }
     try:
         response = requests.post(f"{OLLAMA_API_BASE}/chat", headers=headers, json=payload)
         response.raise_for_status()
         return response.json()
     except requests.exceptions.RequestException as e:
         print(f"Ollama API Error: {e}")
         return {"error": str(e)}
 
 # --- AGENT LOOP ---
 
def run_local_agent():
     print(f"Starting local agent with {MODEL_NAME}...")
     print("Type 'exit' to quit.")
 
     messages = [{"role": "system", "content": SYSTEM_PROMPT}]
 
     while True:
         user_input = input("\nUSER: ")
         if user_input.lower() == 'exit':
             print("Exiting agent.")
             break
         
         # Add user input as a user message
         messages.append({"role": "user", "content": user_input})
 
         while True: # Inner loop to handle tool calls until LLM provides a final answer
             response_json = chat_with_ollama(messages)
 
             if response_json.get("error"):
                 print(f"Agent experienced an error: {response_json['error']}")
                 break # Exit inner loop on error
 
             assistant_response = response_json["message"]["content"]
             messages.append(response_json["message"]) # Add assistant's response to history
 
             print(f"\nASSISTANT: {assistant_response}")
 
             # Check if the assistant wants to call a tool
             if "```json" in assistant_response and "```" in assistant_response:
                 try:
                     # Extract the JSON block
                     json_start = assistant_response.find("```json") + len("```json")
                     json_end = assistant_response.find("```", json_start)
                     tool_call_json_str = assistant_response[json_start:json_end].strip()
                     tool_call = json.loads(tool_call_json_str)
                     
                     tool_name = tool_call["tool"]
                     tool_parameters = tool_call["parameters"]
 
                     if tool_name in AVAILABLE_TOOLS:
                         print(f"AGENT: Calling tool '{tool_name}' with parameters {tool_parameters}")
                         tool_output = AVAILABLE_TOOLS[tool_name](**tool_parameters)
                         print(f"TOOL OUTPUT: {tool_output}")
                         messages.append({"role": "system", "content": f"TOOL_OUTPUT for {tool_name}:\n{tool_output}"})
                         # Continue in the inner loop to let LLM process tool output
                     else:
                         print(f"AGENT: Error: Tool '{tool_name}' not found.")
                         messages.append({"role": "system", "content": f"TOOL_ERROR: Tool '{tool_name}' not found."})
                         break # Exit inner loop if tool not found
                 except json.JSONDecodeError as e:
                     print(f"AGENT: Could not parse tool call JSON: {e}. Raw response:\n{assistant_response}")
                     # If JSON parsing fails, treat as a normal response and break tool loop
                     user_further_instruction = input("AGENT: (JSON parse error) Do you want me to try again or give further instructions? (type your response): ")
                     messages.append({"role": "user", "content": user_further_instruction})
                     break
                 except Exception as e:
                     print(f"AGENT: An error occurred during tool execution: {e}")
                     messages.append({"role": "system", "content": f"TOOL_ERROR: {e}"})
                     break
             else:
                 # If no tool call, LLM has provided a final answer or is thinking
                 break # Exit inner loop, wait for next user input
 
 if __name__ == "__main__":
     # Check if Ollama is running
     try:
         requests.get(f"{OLLAMA_API_BASE}/chat", timeout=2) # Pings /chat, not necessarily /api/tags
     except requests.exceptions.ConnectionError:
         print(f"ERROR: Could not connect to Ollama at {OLLAMA_API_BASE}.")
         print("Please ensure Ollama is running and the model is downloaded.")
         exit(1)
     except Exception as e:
         # Catch other potential errors, e.g., if /chat endpoint doesn't exist but server is up
         pass # Continue assuming server is reachable for /chat below
 
 
     run_local_agent()