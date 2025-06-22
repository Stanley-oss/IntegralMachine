# Integral Machine
## Introduction:
Integral Machine is a system that recognizes mathematical expressions from images and performs integral operations.
It is powered by a front-end interface and a back-end server powered by a trained BTTR model. This system processes handwritten mathematical expressions through image recognition and performs step-by-step symbolic integration calculations.
## Function
1.Recognize handwritten or printed math expressions from images and convert them to LaTeX using a trained BTTR model.
2.Use SymPy for symbolic integration,aotomatic integration. Frontend for uploading images and viewing results, backend for image recognition and computation.
## Setup:
### Backend:
Create a new environment:
```
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
### Frontend:
Install nvm:
For MacOS:
Please refer to https://github.com/nvm-sh/nvm
For Windows:
Download and install https://github.com/coreybutler/nvm-windows
Then run:
```
nvm install 21
uvm use 21
```
## How to Run:
### Backend:
Run in venv:
```
uvicorn app.main:app --reload --port 8000
```
Backend loading is successful and displayed:
```
INFO: Application startup complete.
```
### Frontend:
At the root of the project, run:
```
cd ./integral-machine/
npm run dev
```
Front-end loading is complete and has been displayed.
```
VITE v6.*.*  ready in *** ms
```
Then open the webpage in any browser, have fun!