"""Offline HTML report of declared capabilities, without runtime inspection."""
import argparse
from html import escape
from . import __version__
from .agent_catalog import AGENTS


def render_report(agents=AGENTS):
    cards = []
    model_labels = {"none": "Sem modelo", "optional": "Modelo opcional", "required": "Modelo necessário"}
    for agent in agents:
        capabilities = []
        for capability in agent.capabilities:
            dependencies = ", ".join(capability.dependencies) or "Biblioteca padrão"
            limits = "".join(f"<li>{escape(item)}</li>" for item in capability.limits)
            capabilities.append(
                f"<section><h3>{escape(capability.id)}</h3>"
                f"<p class='badge'>{model_labels[capability.model_use]}</p>"
                f"<p>Dependências: {escape(dependencies)}</p><ul>{limits}</ul></section>"
            )
        cards.append(f"<article><h2>{escape(agent.id)}</h2><p>{escape(agent.description)}</p>"
                     + "".join(capabilities) + "</article>")
    return """<!doctype html>
<html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>GensIA — Catálogo local de agentes</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e7edf7;font:16px/1.65 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:48px 24px}h1{font-size:clamp(32px,6vw,52px);line-height:1.15;margin:12px 0}
h2{font-size:25px;color:#91d9ff;margin:0}h3{font-size:17px;margin-bottom:4px}p{margin:12px 0}
.eyebrow{color:#91d9ff;letter-spacing:.12em;font-weight:700}.notice{border-left:4px solid #f5c46b;padding:16px 24px;background:#202333;margin:28px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:20px}
article{background:#152035;border:1px solid #354661;border-radius:16px;padding:24px;overflow-wrap:anywhere}
section{border-top:1px solid #354661;margin-top:20px}.badge{color:#aceac7;font-weight:600}ul{padding-left:22px}footer{color:#b2bfd2;margin-top:28px}
@media print{:root{color-scheme:light}body{background:white;color:black}article,.notice{background:white;border-color:#555}h2,.eyebrow,.badge,footer{color:#222}article{break-inside:avoid}}
</style></head><body><main>
<header><div class="eyebrow">GENSIA / CATÁLOGO LOCAL</div><h1>Conhece a equipa.</h1>
<p>Capacidades declaradas, dependências e limites dos agentes especializados.</p></header>
<aside class="notice"><strong>Relatório estático — não indica agentes ativos.</strong>
<p>Dependências não verificadas. Nenhuma tarefa é executada ao abrir este ficheiro.
Sem rede, sem documentos pessoais e sem ligação à API.</p></aside>
<div class="grid">""" + "".join(cards) + f"""</div>
<footer>GensIA {escape(__version__)} · Protótipo em desenvolvimento.
<p>Para diagnóstico local, usa <code>python -m gensia.doctor --model NOME</code>.
O diagnóstico não comprova inferência. Este relatório não se atualiza automaticamente.</p></footer>
</main></body></html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gerar catálogo HTML offline no stdout.")
    parser.parse_args(argv)
    print(render_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
