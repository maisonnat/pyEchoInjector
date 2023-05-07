# pyEcho DLL Injector :syringe:

This repository contains a Python-based DLL Injector in progress, which is part of my learning journey. The project explores various aspects such as Windows API, DLL injection, and other interesting concepts. :books:

Feel free to join me in this journey, contribute to the project, and leave a :star: if you find it interesting! :rocket:

## :wrench: Features

- Inject a DLL into a target process
- Unload the DLL from the target process
- Tray icon for easy interaction
- Keyboard shortcuts for convenience
- Utilizes a `.env` file to store configuration

## :computer: Usage

1. Install required dependencies:

```bash
pip install -r requirements.txt


2. Set up your .env file with the following variables:
```bash
DLL_PATH=path\to\your\dll.dll
PROCESS_NAME=YourProcess.exe

3. Run the script:
```bash
python main.py

4. Use the following keyboard shortcuts:
- Alt+I - Inject the DLL
- Alt+U - Unload the DLL
- Alt+C - Close the DLL Injector
- Alt+X - Close the target process and the DLL Injector

## :handshake: Contributing
Contributions are welcome! Feel free to submit issues, create pull requests, or just share your thoughts and suggestions.

## :page_with_curl: License
This project is licensed under the MIT License - see the LICENSE file for details.
