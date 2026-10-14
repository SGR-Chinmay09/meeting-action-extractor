AI Meeting Action-Item Extractor

A locally running AI-powered application that extracts actionable tasks from meeting transcripts, identifies task owners and deadlines, validates the extracted information, and presents the results in an interactive Streamlit dashboard.

1. Project Overview

Meeting discussions often contain important tasks, responsibilities, and deadlines that can be difficult to track manually. This project helps convert meeting transcripts into structured action items.

Key Features

- Extracts action items from meeting transcripts using a local language model.
- Identifies task owners and deadlines when mentioned.
- Normalizes recognizable deadlines into standard date formats.
- Flags incomplete or ambiguous information for manual review.
- Displays extracted action items in an interactive dashboard.
- Allows users to review and edit extracted results.
- Provides confidence scores and validation warnings.
- Supports structured JSON export of the results.

Note: AI-generated results may contain errors. Always verify task owners, deadlines, and action items before using or sharing the extracted data. Confidence scores are heuristic estimates, not calibrated probabilities.

2. Technology Stack

- Python
- Streamlit
- Pandas
- Requests
- llama.cpp
- Qwen2.5-1.5B-Instruct GGUF language model

3. Project Structure

The project source code is organized approximately as follows:

meeting-action-extractor/
├── app.py
├── requirements.txt
├── README.md
├── src/
│   ├── transcript_processor.py
│   ├── action_extractor.py
│   ├── structured_output.py
│   ├── validator.py
│   └── local_llm.py
├── data/
│   └── sample_transcript.txt
├── models/
│   └── qwen2.5-1.5b-instruct-q4_k_m.gguf
└── llama.cpp/
    └── build/
        └── bin/
            └── llama-server

The model file and compiled llama.cpp binaries may not be included in the submitted ZIP. They can be downloaded and built separately using the instructions below.

4. Prerequisites

Before running the project, install:

- Python 3.10 or a compatible version supported by the project's dependencies.
- Git.
- CMake.
- A C/C++ compiler and build tools.
- Internet access for downloading dependencies and the language model.
- Sufficient disk space and RAM for the model and runtime.

The commands below primarily target macOS. Windows and Linux users may need operating-system-specific setup commands.

5. Extract the Project

1. Download the ZIP file.
2. Extract it to a convenient location.
3. Open the extracted "meeting-action-extractor" folder in VS Code.
4. Open a terminal in that folder.

Make sure "app.py", "requirements.txt", "README.md", and the "src/" folder are present.

6. Set Up the Python Environment

Create a virtual environment:

python3 -m venv venv

Activate it on macOS or Linux:

source venv/bin/activate

Install the Python dependencies:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

The environment should now contain the packages required by the Streamlit application.

If a package installation fails, check the Python version and the error message before continuing.

7. Download and Build llama.cpp

Step 1: Obtain llama.cpp

If the project does not already contain a usable "llama.cpp" source directory, run:

git clone https://github.com/ggml-org/llama.cpp.git

If the directory already exists, use that directory instead of cloning it again.

Step 2: Install build tools

On macOS, install Apple's command-line tools if they are not already installed:

xcode-select --install

Install CMake using Homebrew if needed:

brew install cmake

If Homebrew is not installed, follow the installation instructions at https://brew.sh.

Step 3: Build llama.cpp

From the project root, run:

cmake -S llama.cpp -B llama.cpp/build
cmake --build llama.cpp/build --config Release -j 2

Building may take several minutes. Wait for the commands to complete successfully.

Verify that the server executable exists:

ls llama.cpp/build/bin/llama-server

If the build fails or the server reports a missing dynamic library, review the build output and rebuild using the official llama.cpp instructions. Do not assume the server is ready until it starts successfully.

Official repository: https://github.com/ggml-org/llama.cpp

8. Download the Qwen Language Model

This application uses the Qwen2.5-1.5B-Instruct model in GGUF format.

1. Open the model repository:
   
   https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF

2. Download the file:
   
   "qwen2.5-1.5b-instruct-q4_k_m.gguf"

3. Create a "models/" directory in the project root if it does not exist.

4. Place the downloaded model inside it.

The expected model path is:

models/qwen2.5-1.5b-instruct-q4_k_m.gguf

Ensure that the filename matches the one used in the server command.

9. Start the Local AI Server

Open a terminal in the project root.

Run:

./llama.cpp/build/bin/llama-server \
  -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8081 \
  -c 2048

This starts the model server locally on port "8081".

Keep this terminal open while using the application. The server must be running before the application requests AI extraction.

The application expects the API endpoint:

http://127.0.0.1:8081/v1/chat/completions

To check whether the server is responding, open this address in a browser:

http://127.0.0.1:8081/v1/models

A successful response should contain model information in JSON format.

If the server fails to start, check the model path, executable path, build status, and error messages in the terminal.

10. Configure the Application

Open "src/local_llm.py" and verify that the API configuration points to the local server:

LLAMA_API_URL = "http://127.0.0.1:8081/v1/chat/completions"

The model name used in the API request should be compatible with the local llama.cpp server configuration.

Do not change the endpoint unless the server is configured to use a different address or port.

11. Run the Streamlit Application

Keep the AI server running in the first terminal.

Open a second terminal in the project root.

Activate the Python environment:

source venv/bin/activate

Start the dashboard:

python -m streamlit run app.py

Streamlit will display a local URL, usually:

http://localhost:8501

Open that URL in your browser to use the application.

Keep both terminals open while using the AI extraction features.

12. How to Use the Application

1. Start the local AI server.
2. Start the Streamlit application.
3. Open the dashboard in your browser.
4. Enter or load a meeting transcript.
5. Set the meeting date if the interface provides that option.
6. Run the action-item extraction process.
7. Review the extracted tasks, owners, deadlines, and confidence scores.
8. Check all validation warnings and manually correct inaccurate information.
9. Export the reviewed results as JSON if required.

The exact controls depend on the version of the dashboard included in the submitted source code.

13. Troubleshooting

Error: "streamlit: command not found"

Activate the virtual environment and install the dependencies:

source venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py

Error: Connection refused on port 8081

The local AI server may not be running.

- Start the llama.cpp server first.
- Check that it is listening on port "8081".
- Confirm that "src/local_llm.py" uses the correct API endpoint.

Error: Model file not found

Check that the model exists at:

models/qwen2.5-1.5b-instruct-q4_k_m.gguf

Ensure the filename and path match the server command.

Error: "libllama-server-impl.dylib" not found

The llama.cpp build may be incomplete or its executable and libraries may come from different build locations.

Reconfigure and rebuild from the correct source directory:

cmake -S llama.cpp -B llama.cpp/build
cmake --build llama.cpp/build --config Release -j 2

Then verify that the generated server and its required libraries are present.

Error: "cmake: command not found"

Install CMake and ensure that it is available in the terminal's PATH. On macOS with Homebrew:

brew install cmake

Extraction produces incorrect or incomplete results

- Use a clear, readable transcript.
- Check that the local server is responding.
- Verify the transcript date.
- Review missing or ambiguous owners and deadlines manually.
- Remember that model-generated output is not guaranteed to be correct.

14. Important Notes

- The application uses a local language model rather than requiring a hosted LLM API.
- The local server must be running for AI extraction to work.
- The model and llama.cpp runtime may need to be downloaded or built separately.
- The first setup requires internet access, but local inference can run without an external LLM API once everything is installed.
- Resource requirements vary by operating system and hardware.
- Do not include confidential meeting transcripts in shared demonstrations unless authorized.

15. Future Enhancements

Potential improvements include:

- Support for additional transcript formats.
- Improved owner and deadline verification.
- Integration with calendars and task-management systems.
- Persistent meeting history.
- More robust evaluation of extraction accuracy.
- Support for additional local language models.

16. Acknowledgment

This project demonstrates the use of local language models, Python, and Streamlit to help automate meeting action-item extraction and review.

Thank you for reviewing this prototype.
# meeting-action-extractor
ai powered meeting action item extraction using a local language model and streamlit
