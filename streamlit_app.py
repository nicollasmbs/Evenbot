import streamlit as st
import google.generativeai as genai
import time
import json
from datetime import datetime

# === Configuração da API Gemini ===
def configurar_api_chave(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name="gemini-2.0-flash")

GEMINI_API_KEY = "AIzaSyDhulnbWq1ernvRJ2i9PR2PYm9kJV8QbLM"
model = configurar_api_chave(GEMINI_API_KEY)

# === Função para gerar texto com retry e delay ===
def gerar_com_resiliencia(prompt: str, tentativas=3, delay=10) -> str:
    for tentativa in range(tentativas):
        try:
            response = model.generate_content(prompt)
            time.sleep(1)  # Pequena pausa para evitar throttling
            return response.text
        except Exception as e:
            if "429" in str(e):
                time.sleep(delay)
            else:
                break
    raise Exception("Falha ao gerar conteúdo com a API Gemini após múltiplas tentativas.")

# === Extrair tipo, cidade e data da pergunta via IA ===
def interpretar_pergunta(pergunta: str):
    prompt = f"""
Extraia da pergunta o tipo de evento (exemplo: show, festa, feira, programação), a cidade e a data (se houver) mencionadas.

Responda no formato JSON exatamente assim:
{{"tipo": "[tipo]", "cidade": "[cidade]", "data": "[data]"}} 

Se não houver data mencionada, deixe o campo "data" vazio.

Exemplo:
Pergunta: "Vai ter show em Caruaru no dia 23 de junho de 2025?"
Resposta: {{"tipo": "show", "cidade": "Caruaru", "data": "2025-06-23"}}

Pergunta: "{pergunta}"
Resposta:
"""
    texto = gerar_com_resiliencia(prompt)
    
    try:
        inicio = texto.find('{')
        fim = texto.rfind('}') + 1
        json_str = texto[inicio:fim]
        dados = json.loads(json_str)
        
        tipo = dados.get("tipo", "").lower().strip() or None
        cidade = dados.get("cidade", "").strip() or None
        data = dados.get("data", "").strip() or None
        
        termos_genericos = {"evento", "eventos", "programação", "agenda", "agenda cultural", "festa"}
        if tipo in termos_genericos:
            tipo = None
        
        return cidade, tipo, data
    except Exception:
        return None, None, None

# === Função auxiliar para comparar datas considerando só o dia, ignorando zeros à esquerda ===
def comparar_datas(data_filtro, data_evento):
    try:
        import re
        def extrair_dia(data_str):
            if not data_str:
                return None
            numeros = re.findall(r'\d+', data_str)
            if not numeros:
                return None
            return int(numeros[0])
        
        dia_filtro = extrair_dia(data_filtro)
        dia_evento = extrair_dia(data_evento)
        
        if dia_filtro is None or dia_evento is None:
            return False
        
        return dia_filtro == dia_evento
    except Exception as e:
        print(f"Erro comparar datas: {e}")
        return False

# === Buscar eventos locais filtrando por cidade, tipo e data ===
def buscar_eventos(cidade, tipo=None, data=None, arquivo_eventos="programacao_sao_joao_caruaru.json"):
    try:
        with open(arquivo_eventos, "r", encoding="utf-8") as f:
            eventos = json.load(f)

        cidade = cidade.lower()
        tipo = tipo.lower() if tipo else None

        termos_relacionados = {
            "show": ["show", "banda", "cantor", "apresentação", "musical"],
            "festa": ["festa", "balada", "arraial", "forró", "são joão"],
            "feira": ["feira", "artesanato", "gastronomia"],
            "programação": [],
        }

        termos_tipo = termos_relacionados.get(tipo, [tipo]) if tipo else []

        eventos_filtrados = []
        for evento in eventos:
            cidade_evento = evento.get("Nome da cidade", "").lower()
            nome_evento = evento.get("nome", "").lower()
            polo_evento = evento.get("polo", "").lower()
            data_evento = evento.get("data", "").strip()

            if cidade_evento != cidade:
                continue

            if tipo:
                if not any(t in nome_evento or t in polo_evento for t in termos_tipo):
                    continue

            if data:
                if not comparar_datas(data, data_evento):
                    continue

            eventos_filtrados.append(evento)

        return eventos_filtrados

    except Exception as e:
        print(f"Erro ao buscar eventos: {e}")
        return []

# === Gerar resposta amigável para o usuário (no formato pedido) ===
def gerar_resposta(cidade, tipo, eventos):
    if not eventos:
        if tipo:
            return f"Desculpe, não encontrei eventos do tipo '{tipo}' em {cidade} no momento. 😕"
        else:
            return f"Desculpe, não encontrei eventos em {cidade} no momento. 😕"

    agrupados = {}
    for evento in eventos:
        polo = evento.get("polo", "Local desconhecido").strip()
        if polo.lower() == "palco principal":
            polo = "pátio de eventos"

        data_evento = evento.get("data", "Data desconhecida")
        nome = evento.get("nome", "Artista desconhecido")

        chave = (polo, data_evento)
        if chave not in agrupados:
            agrupados[chave] = []
        agrupados[chave].append(nome)

    resposta = ""
    for (polo, data_evento), nomes in agrupados.items():
        resposta += f"{polo}\n"
        resposta += f"{data_evento}\n"
        for nome in nomes:
            resposta += f"- {nome}\n"
        resposta += "\n"

    return resposta.strip()

# === Função principal do bot ===
def evenbot(pergunta):
    cidade, tipo, data = interpretar_pergunta(pergunta)
    if not cidade:
        return "Por favor, informe uma cidade para que eu possa buscar os eventos."
    eventos = buscar_eventos(cidade, tipo, data)
    resposta = gerar_resposta(cidade, tipo, eventos)
    return resposta

# === Interface Streamlit ===
def main():
    st.set_page_config(page_title="EvenBot Chat", page_icon="🎉")
    st.title("🎉 EvenBot - Chat de Eventos")

    st.write("Pergunte sobre a programação do São João em Caruaru. Exemplo: Qual a programação no dia 31?")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    pergunta = st.text_input("Digite sua pergunta:", key="pergunta_input")

    if st.button("Enviar") and pergunta:
        with st.spinner("Procurando eventos..."):
            try:
                resposta = evenbot(pergunta)
                # Guarda só a resposta para exibir
                st.session_state.chat_history = [("EvenBot", resposta)]
            except Exception as e:
                st.error(f"Erro: {e}")

    for autor, mensagem in st.session_state.chat_history:
        # Exibir só a resposta, sem prefixo "EvenBot"
        st.markdown(mensagem)

if _name_ == "_main_":
    main()