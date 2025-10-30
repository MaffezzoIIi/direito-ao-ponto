from typing import Dict
from pathlib import Path
from docxtpl import DocxTemplate
import datetime

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_peticao_inicial_cobranca(data: Dict) -> str:
    """
    Renderiza o template docx com os dados do JSON.
    Retorna o caminho do arquivo gerado.
    """
    tpl_path = TEMPLATES_DIR / "peticao_inicial_cobranca.docx"
    doc = DocxTemplate(str(tpl_path))

    # Contexto para o template (placeholders)
    ctx = {
        "foro": data.get("foro"),
        "autor_nome": data["autor"]["nome"],
        "autor_cpf": data["autor"].get("cpf", ""),
        "autor_endereco": data["autor"].get("endereco", ""),
        "reu_nome": data["reu"]["nome"],
        "reu_cnpj": data["reu"].get("cnpj", ""),
        "reu_endereco": data["reu"].get("endereco", ""),
        "fatos": data.get("fatos", ""),
        "valor_causa": f"R$ {data.get('valor_causa', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "pedidos": data.get("pedidos", []),
        "provas": data.get("provas", []),
        "hoje": datetime.date.today().strftime("%d/%m/%Y"),
    }

    doc.render(ctx)
    out_path = OUTPUTS_DIR / f"Peticao_Inicial_Cobranca_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(out_path))
    return str(out_path)
