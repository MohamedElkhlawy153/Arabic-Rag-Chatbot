Steup instructions :
Pc programmes needed :
1. Microsoft tool C++ : download builder from microsoft websit and then download and install C++ package it is 7gb for windows 11 
2. enable win32 longpath :Press Win + R, type gpedit.msc, and press Enter.
Navigate to:
Local Computer Policy > Computer Configuration > Administrative Templates > System > Filesystem.
Double-click Enable Win32 long paths.
Select Enabled, then click OK.
Restart your computer.
3. Node.js :download the last version from the website 

Terminal in vs code :

1. python -m venv .venv

2. venv\Scripts\activate

3. python pip install --upgrade pip

4. pip install -r requirements.txt


Backend : 
1. Make copy of .env.example as .env 
edit api keys for cohere and gemini with ur own , remember to edit at bottom of .env file backend_core_origin with ur front localhost to fetch data without errors   

3. open terminal ingerated in ur backend and make it run with venv :
   venv\Scripts\activate
cd "D:\MrTyson\Data sciences projects\Fixed solutions\Call Center AI outbound calls and chat bot\arabic-rag-chatbot-Main\backend"

uvicorn app.main:app --reload             

Frontend :
1. make copy of .env.example in frontend folder as .env 
leave it localhost 8000 as it is 
2. same as backend open another terminal :
       venv\Scripts\activate
cd "D:\MrTyson\Data sciences projects\Fixed solutions\Call Center AI outbound calls and chat bot\arabic-rag-chatbot-Main\frontend"

npm run dev

note if u tried to use main folder without specifie the folder it gives error  bec it will not pick up the .env in backend folder 