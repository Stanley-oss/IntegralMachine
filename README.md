# Integral Machine
## Setup:
### First Install PassleOCR:
https://paddlepaddle.github.io/PaddleOCR/main/en/quick_start.html
### Then:
最好先
```
python -m venv venv
.\venv\Scripts\activate
```
然后安装库
```
pip install astunparse sympy latex2sympy2 fastapi setuptools uvicorn pydantic
```
### Frontend:
安装nvm
安装node.js
当npm -v和node -v都能输出版本号就行了
## How to Run:
### Backend:
在venv下运行:
```
uvicorn app.main:app --reload --port 8000
```
后端加载成功显示INFO: Application startup complete.
### Frontend:
在integral-machine目录下运行:
```
npm run dev
```
前端加载成功显示
VITE v6.*.*  ready in *** ms
然后打开网页开始玩...