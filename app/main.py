from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/webhook")
async def webhook(req: Request):
    # まずはVerifyを通すために200を返すだけでOK
    return JSONResponse({"ok": True}, status_code=200)

