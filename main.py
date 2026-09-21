import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from seleniumbase import SB

app = FastAPI()

# Se você definir a variável de ambiente API_TOKEN no easypanel, o serviço
# passa a exigir o header X-Token em toda chamada. Deixe em branco pra não exigir nada.
API_TOKEN = os.environ.get("API_TOKEN", "")
# Opcional: defina PROXY_URL no easypanel no formato "usuario:senha@host:porta"
# pra rotear as chamadas por um proxy residencial, caso o bloqueio seja por IP.
PROXY_URL = os.environ.get("PROXY_URL", "")


class ScrapeRequest(BaseModel):
    url: str
    wait_selector: Optional[str] = None
    timeout: int = 12          # segundos esperando o wait_selector aparecer
    reconnect_time: int = 4    # segundos que o modo UC espera antes de "reconectar" (evasão)


@app.post("/content")
def scrape(req: ScrapeRequest, x_token: Optional[str] = Header(default=None)):
    if API_TOKEN and x_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        sb_kwargs = {
            "uc": True,
            "xvfb": True,
            "chromium_arg": "--blink-settings=imagesEnabled=false",
        }
        if PROXY_URL:
            sb_kwargs["proxy"] = PROXY_URL

        with SB(**sb_kwargs) as sb:
            sb.activate_cdp_mode(req.url)
            sb.sleep(req.reconnect_time)

            if req.wait_selector:
                try:
                    sb.wait_for_element(req.wait_selector, timeout=req.timeout)
                except Exception:
                    # Mesmo comportamento do "bestAttempt" do Browserless:
                    # se o seletor não aparecer, devolve o HTML do jeito que está
                    # em vez de estourar erro — assim você ainda consegue ver
                    # se caiu numa tela de bloqueio, por exemplo.
                    pass

            html = sb.get_page_source()

        return {"data": html}

    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}
