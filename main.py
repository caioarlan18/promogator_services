import os
import threading
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

# Limita quantas sessões de Chrome rodam ao mesmo tempo nesse servidor.
# Cada sessão consome ~300-500MB de RAM — sem esse limite, várias chamadas
# simultâneas (ou retries se acumulando) podem esgotar a memória do VPS
# e derrubar o servidor inteiro, não só esse serviço.
MAX_SESSOES_SIMULTANEAS = int(os.environ.get("MAX_SESSOES_SIMULTANEAS", "1"))
_semaforo_sessoes = threading.Semaphore(MAX_SESSOES_SIMULTANEAS)


class ScrapeRequest(BaseModel):
    url: str
    wait_selector: Optional[str] = None
    timeout: int = 12          # segundos esperando o wait_selector aparecer
    reconnect_time: int = 4    # segundos que o modo UC espera antes de "reconectar" (evasão)
    use_proxy: bool = False    # só ativa o proxy residencial quando explicitamente pedido (ex: Amazon)


def detectar_pagina_ruim(html: str) -> Optional[str]:
    """Retorna uma descrição do problema se o HTML for uma tela de erro
    (do Chrome, bloqueio da Amazon, ou captcha não resolvido) em vez de conteúdo real."""
    if 'id="main-frame-error"' in html:
        return "Erro de rede do Chrome (proxy/túnel falhou nessa tentativa)"
    if "Cachorros da Amazon" in html or "Amazon.com.br Algo deu errado" in html:
        return "Bloqueio de bot da Amazon (tela de erro genérica)"
    if 'id="altcha_checkbox"' in html or "Captcha Magalu" in html:
        return "Captcha ALTCHA não resolvido (Magalu)"
    return None


def tentar_resolver_altcha(sb, espera: int = 6) -> None:
    """Se a página atual tiver um captcha ALTCHA (checkbox 'I'm not a robot'),
    clica nele e espera a verificação + redirecionamento acontecerem."""
    try:
        if sb.is_element_present("#altcha_checkbox"):
            sb.click("#altcha_checkbox")
            sb.sleep(espera)
    except Exception:
        # Se não conseguir clicar por qualquer motivo, segue o fluxo normal —
        # o detectar_pagina_ruim mais abaixo vai pegar e contar como falha
        pass


@app.post("/content")
def scrape(req: ScrapeRequest, x_token: Optional[str] = Header(default=None)):
    if API_TOKEN and x_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")

    TENTATIVAS_INTERNAS = 3
    ultimo_problema = None

    for tentativa in range(1, TENTATIVAS_INTERNAS + 1):
        try:
            sb_kwargs = {
                "uc": True,
                "xvfb": True,
                "chromium_arg": "--blink-settings=imagesEnabled=false",
            }
            if PROXY_URL and req.use_proxy:
                sb_kwargs["proxy"] = PROXY_URL

            with _semaforo_sessoes:
                with SB(**sb_kwargs) as sb:
                    sb.activate_cdp_mode(req.url)
                    sb.sleep(req.reconnect_time)

                    tentar_resolver_altcha(sb)

                    if req.wait_selector:
                        try:
                            sb.wait_for_element(req.wait_selector, timeout=req.timeout)
                        except Exception:
                            pass

                    html = sb.get_page_source()

            problema = detectar_pagina_ruim(html)
            if not problema:
                # Deu certo — devolve já, sem gastar as tentativas restantes
                return {"data": html, "tentativas": tentativa}

            ultimo_problema = problema
            # Continua pro próximo laço, que abre uma sessão nova (IP novo)

        except Exception as e:
            ultimo_problema = str(e)

    # Esgotou as tentativas internas sem sucesso
    raise HTTPException(
        status_code=502,
        detail=f"Falhou após {TENTATIVAS_INTERNAS} tentativas internas. Último problema: {ultimo_problema}",
    )


@app.get("/health")
def health():
    return {"status": "ok"}
