from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from paddleocr import FormulaRecognition
import base64
import numpy as np
import cv2
from typing import List, Dict, Any
from . import integral

class HandwritingRequest(BaseModel):
    image: str  # Base64编码的图片

class HandwritingResponse(BaseModel):
    latex: str  # 识别到的LaTeX公式

class CalculationRequest(BaseModel):
    formula: str  # 输入的LaTeX公式

class Step(BaseModel):
    rule: str
    before: str
    after: str

class CalculationResponse(BaseModel):
    answer: str
    steps: List[Step]

app = FastAPI()

solver = integral.IntegralSolver()

print("Loading handwriting recognition model...")
formula_recognizer = FormulaRecognition(model_name="PP-FormulaNet_plus-M")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/handwriting", response_model=HandwritingResponse)
async def recognize_handwriting(request: HandwritingRequest):
    try:
        data = request.image
        # 补齐Base64字符串
        padding = len(data) % 4
        if padding != 0:
            data += '=' * (4 - padding)
        image_bytes = base64.b64decode(data)
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        output = formula_recognizer.predict(input=img)
        latex = output[0].json['res']['rec_formula']
        return HandwritingResponse(latex=latex)
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Error: {e}")

@app.post("/api/calculate", response_model=CalculationResponse)
async def calculate_formula_api(request: CalculationRequest):
    try:
        py_expr = solver.latex_to_str(request.formula)
        result = solver.integral(py_expr)
        return CalculationResponse(
            answer=result.get('answer', ''),
            steps=[Step(**step) for step in reversed(result.get('steps', []))]
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error: {e}")
