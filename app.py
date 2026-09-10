from datetime import datetime
from io import BytesIO
import json
import os
import re
import urllib.parse
import pandas as pd
import qrcode
import streamlit as st

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Avaliação de Treinamentos",
    page_icon="📝",
    layout="wide",
)

ARQUIVO_PROVAS = "provas_bd.json"
ARQUIVO_RESULTADOS = "resultados_bd.csv"

# Prova padrão inicial (baseada no documento 5S)
PROVA_PADRAO_5S = {
    "Programa 5S - Habilidades Profissionais": {
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "questoes": [
            {
                "id": 1,
                "pergunta": "Qual é o foco principal do Senso de Utilização (Seiri)?",
                "opcoes": [
                    "A) Manter o ambiente decorado e organizado.",
                    "B) Eliminar itens desnecessários e reduzir distrações.",
                    "C) Praticar atividades físicas no ambiente.",
                    "D) Criar rotinas rígidas de limpeza.",
                ],
                "resposta_correta": "B) Eliminar itens desnecessários e reduzir distrações.",
            },
            {
                "id": 2,
                "pergunta": "O Senso de Ordenação (Seiton) prega que:",
                "opcoes": [
                    "A) Tudo deve ficar guardado em armários fechados.",
                    "B) Cada coisa deve ter seu lugar para economizar tempo.",
                    "C) A limpeza deve ser feita diariamente.",
                    "D) Apenas ferramentas novas devem ser utilizadas.",
                ],
                "resposta_correta": "B) Cada coisa deve ter seu lugar para economizar tempo.",
            },
            {
                "id": 3,
                "pergunta": "No Senso de Limpeza (Seiso), a responsabilidade pela conservação dos equipamentos é:",
                "opcoes": [
                    "A) Exclusiva da equipe de limpeza.",
                    "B) Do gerente de operações.",
                    "C) Coletiva de todos os usuários dos recursos.",
                    "D) Apenas de quem sujou o equipamento.",
                ],
                "resposta_correta": "C) Coletiva de todos os usuários dos recursos.",
            },
            {
                "id": 4,
                "pergunta": "O Senso de Saúde (Seiketsu) abrange práticas como:",
                "opcoes": [
                    "A) Apenas fazer exames admissionais.",
                    "B) Hábitos saudáveis, cuidados com o corpo e mente.",
                    "C) Focar exclusivamente no desempenho de máquinas.",
                    "D) Evitar pausas durante a rotina de trabalho.",
                ],
                "resposta_correta": "B) Hábitos saudáveis, cuidados com o corpo e mente.",
            },
            {
                "id": 5,
                "pergunta": "O Senso de Autodisciplina (Shitsuke) é definido por:",
                "opcoes": [
                    "A) Cumprir regras apenas sob supervisão direta.",
                    "B) Criar novos hábitos e manter a consistência continuamente.",
                    "C) Nunca errar nas tarefas diárias.",
                    "D) Ter punições para quem descumprir procedimentos.",
                ],
                "resposta_correta": "B) Criar novos hábitos e manter a consistência continuamente.",
            },
        ],
    }
}


# -----------------------------------------------------------------------------
# PERSISTÊNCIA DE DADOS E UTILITÁRIOS
# -----------------------------------------------------------------------------
def carregar_provas():
    if os.path.exists(ARQUIVO_PROVAS):
        try:
            with open(ARQUIVO_PROVAS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if dados:
                    return dados
        except Exception:
            pass

    # Caso o arquivo não exista ou esteja vazio, cria a prova padrão
    salvar_todas_provas(PROVA_PADRAO_5S)
    return PROVA_PADRAO_5S


def salvar_todas_provas(provas_dict):
    with open(ARQUIVO_PROVAS, "w", encoding="utf-8") as f:
        json.dump(provas_dict, f, ensure_ascii=False, indent=4)


def salvar_prova(titulo_formacao, questoes):
    provas = carregar_provas()
    provas[titulo_formacao] = {
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "questoes": questoes,
    }
    salvar_todas_provas(provas)


def carregar_resultados():
    if os.path.exists(ARQUIVO_RESULTADOS):
        try:
            return pd.read_csv(ARQUIVO_RESULTADOS, encoding="utf-8")
        except Exception:
            pass

    colunas = [
        "Data_Hora",
        "Formacao",
        "Nome",
        "Sobrenome",
        "Nome_Completo",
        "Unidade",
        "Nota",
        "Acertos",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "Q5",
    ]
    return pd.DataFrame(columns=colunas)


def salvar_resultado(novo_resultado_dict):
    df_existente = carregar_resultados()
    df_novo = pd.DataFrame([novo_resultado_dict])
    df_atualizado = pd.concat([df_existente, df_novo], ignore_index=True)
    df_atualizado.to_csv(ARQUIVO_RESULTADOS, index=False, encoding="utf-8")


def gerar_qrcode(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1F4E78", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def parse_texto_simples(texto):
    """Lê o texto gerado pelo ChatGPT/Gemini e transforma em lista de questões."""
    questoes = []
    blocos = re.split(r"\n(?=\d+[\.\)])", texto.strip())

    for b in blocos:
        linhas = [l.strip() for l in b.strip().split("\n") if l.strip()]
        if len(linhas) >= 6:
            pergunta = re.sub(r"^\d+[\.\)]\s*", "", linhas[0])
            opcoes = [linhas[1], linhas[2], linhas[3], linhas[4]]
            resp_linha = linhas[5]
            resp_correta = re.sub(
                r"^Resposta:\s*", "", resp_linha, flags=re.IGNORECASE
            ).strip()

            questoes.append(
                {
                    "id": len(questoes) + 1,
                    "pergunta": pergunta,
                    "opcoes": opcoes,
                    "resposta_correta": resp_correta,
                }
            )
    return questoes


def exportar_excel(df_resultados):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_resultados.to_excel(
            writer, sheet_name="Resultados_Detalhados", index=False
        )
        if not df_resultados.empty:
            ranking = (
                df_resultados.groupby(
                    ["Formacao", "Nome_Completo", "Unidade"]
                )["Nota"]
                .max()
                .reset_index()
                .sort_values(by=["Formacao", "Nota"], ascending=[True, False])
            )
            ranking.to_excel(
                writer, sheet_name="Ranking_Por_Formacao", index=False
            )
    return output.getvalue()


# -----------------------------------------------------------------------------
# ROTEAMENTO DA APLICAÇÃO (ALUNO vs INSTRUTOR)
# -----------------------------------------------------------------------------
params = st.query_params
prova_param = params.get("prova_id", None)
provas_cadastradas = carregar_provas()

if prova_param:
    # Decodificação segura do parâmetro recebido via URL
    formacao_nome = urllib.parse.unquote(prova_param).strip()

    # =========================================================================
    # MÓDULO DO ALUNO (ACESSO VIA QR CODE)
    # =========================================================================
    st.header("📝 Avaliação de Conhecimento")
    st.subheader(f"Formação: **{formacao_nome}**")
    st.caption("Responda às 5 questões abaixo (20 pontos cada). Total: 100 pts.")
    st.divider()

    # Busca permissiva para ignorar diferenças de maiúsculas/minúsculas
    chave_encontrada = None
    for chave in provas_cadastradas.keys():
        if chave.strip().lower() == formacao_nome.lower():
            chave_encontrada = chave
            break

    if not chave_encontrada:
        st.error("⚠️ A prova solicitada não foi encontrada no banco de dados.")
        st.info("Por favor, verifique se a prova foi salva no painel do instrutor.")
    else:
        questoes = provas_cadastradas[chave_encontrada]["questoes"]

        with st.form(key="form_aluno"):
            st.markdown("### 👤 Identificação do Aluno")
            col_a, col_b = st.columns(2)
            with col_a:
                nome = st.text_input("Nome:*")
            with col_b:
                sobrenome = st.text_input("Sobrenome:*")

            unidade = st.text_input("Curso / Unidade / Turma:*")

            st.divider()
            st.markdown("### ❓ Questões")

            respostas = {}
            for idx, q in enumerate(questoes, 1):
                st.markdown(f"**{idx}. {q['pergunta']}**")
                respostas[idx] = st.radio(
                    label=f"q_{idx}",
                    options=q["opcoes"],
                    key=f"q_{idx}",
                    index=None,
                    label_visibility="collapsed",
                )
                st.write("")

            bot_submeter = st.form_submit_button(
                "📥 Enviar Respostas", type="primary", use_container_width=True
            )

        if bot_submeter:
            if not nome.strip() or not sobrenome.strip() or not unidade.strip():
                st.error("⚠️ Preencha Nome, Sobrenome e Unidade.")
            elif None in respostas.values():
                st.error("⚠️ Responda todas as 5 questões antes de enviar.")
            else:
                acertos = 0
                detalhes_q = {}
                for idx, q in enumerate(questoes, 1):
                    resp = respostas[idx]
                    correta = q["resposta_correta"]
                    ok = resp == correta
                    if ok:
                        acertos += 1
                    detalhes_q[f"Q{idx}"] = f"{'OK' if ok else 'ERRO'} ({resp})"

                nota = acertos * 20
                nome_comp = f"{nome.strip().title()} {sobrenome.strip().title()}"

                registro = {
                    "Data_Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Formacao": chave_encontrada,
                    "Nome": nome.strip().title(),
                    "Sobrenome": sobrenome.strip().title(),
                    "Nome_Completo": nome_comp,
                    "Unidade": unidade.strip(),
                    "Nota": nota,
                    "Acertos": f"{acertos}/5",
                    "Q1": detalhes_q["Q1"],
                    "Q2": detalhes_q["Q2"],
                    "Q3": detalhes_q["Q3"],
                    "Q4": detalhes_q["Q4"],
                    "Q5": detalhes_q["Q5"],
                }
                salvar_resultado(registro)

                st.balloons()
                st.success("🎉 Prova enviada com sucesso!")

                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Nota Final", f"{nota} / 100 pts")
                col_m2.metric("Acertos", f"{acertos} de 5")

                st.divider()
                st.markdown(f"### 🏆 Ranking da Formação: **{chave_encontrada}**")

                df_todos = carregar_resultados()
                df_form = df_todos[df_todos["Formacao"] == chave_encontrada].copy()

                if not df_form.empty:
                    df_rank = df_form.sort_values(
                        by=["Nota", "Data_Hora"], ascending=[False, True]
                    ).reset_index(drop=True)
                    df_rank.index += 1
                    st.dataframe(
                        df_rank[
                            ["Nome_Completo", "Unidade", "Nota", "Acertos"]
                        ].rename(
                            columns={
                                "Nome_Completo": "Aluno",
                                "Unidade": "Curso/Unidade",
                            }
                        ),
                        use_container_width=True,
                    )

else:
    # =========================================================================
    # MÓDULO DO INSTRUTOR / ADMINISTRADOR
    # =========================================================================
    st.title("⚙️ Painel do Instrutor")

    tab_criar, tab_provas, tab_resultados = st.tabs(
        [
            "✨ Criar Prova (Copiar e Colar)",
            "📋 Provas & QR Code",
            "📊 Resultados & Excel",
        ]
    )

    with tab_criar:
        st.subheader("1. Identificação")
        nome_form = st.text_input(
            "Nome da Formação:",
            placeholder="Ex: Programa 5S - Habilidades Profissionais",
        )

        st.subheader("2. Gerar Prompt para o ChatGPT/Gemini")
        resumo_aula = st.text_area(
            "Cole o resumo da sua aula aqui:",
            height=120,
            placeholder="Ex: Treinamento sobre os 5 Sensos (Utilização, Ordenação, Limpeza, Saúde, Autodisciplina)...",
        )

        prompt_pronto = f"""Você é um instrutor especialista. Com base no resumo abaixo, crie exatamente 5 questões de múltipla escolha.
Cada questão deve ter 4 opções (A, B, C, D) e indicar a resposta correta.

RESUMO DA AULA:
{resumo_aula if resumo_aula else '[Cole seu resumo aqui]'}

RESPONDA EXATAMENTE NESTE FORMATO (sem adicionar texto antes ou depois):

1. Texto da primeira pergunta?
A) Opção 1
B) Opção 2
C) Opção 3
D) Opção 4
Resposta: A) Opção 1

2. Texto da segunda pergunta?
A) Opção 1
B) Opção 2
C) Opção 3
D) Opção 4
Resposta: B) Opção 2

3. Texto da terceira pergunta?
A) Opção 1
B) Opção 2
C) Opção 3
D) Opção 4
Resposta: C) Opção 3

4. Texto da quarta pergunta?
A) Opção 1
B) Opção 2
C) Opção 3
D) Opção 4
Resposta: D) Opção 4

5. Texto da quinta pergunta?
A) Opção 1
B) Opção 2
C) Opção 3
D) Opção 4
Resposta: A) Opção 1"""

        st.info("💡 **Passo 1:** Copie o texto do quadro abaixo e cole no ChatGPT ou Gemini:")
        st.code(prompt_pronto, language="markdown")

        st.subheader("3. Importar Resposta da IA")
        resposta_ia = st.text_area(
            "💡 **Passo 2:** Cole aqui a resposta gerada pela IA:",
            height=200,
            placeholder="1. Pergunta...\nA) ...\nB) ...\nC) ...\nD) ...\nResposta: A) ...",
        )

        if st.button("💾 Salvar Prova e Gerar QR Code", type="primary"):
            if not nome_form.strip():
                st.error("⚠️ Preencha o nome da formação.")
            elif not resposta_ia.strip():
                st.error("⚠️ Cole a resposta gerada pela IA.")
            else:
                parsed = parse_texto_simples(resposta_ia.strip())
                if len(parsed) == 5:
                    salvar_prova(nome_form.strip(), parsed)
                    st.success(f"🎉 Prova '{nome_form.strip()}' cadastrada com sucesso!")
                    st.rerun()
                else:
                    st.error(
                        f"⚠️ Foram identificadas {len(parsed)} questões. O formato precisa ter exatamente 5 questões no modelo exigido."
                    )

    with tab_provas:
        if not provas_cadastradas:
            st.info("Nenhuma prova cadastrada.")
        else:
            formacao_sel = st.selectbox(
                "Selecione a Formação:", list(provas_cadastradas.keys())
            )

            if formacao_sel:
                st.divider()
                st.subheader("📲 QR Code de Acesso")

                # URL base ajustada
                url_padrao = "https://cqtfxtjeduyxc.streamlit.app"
                
                app_url_base = st.text_input(
                    "URL do Streamlit Cloud (Confira se é o link do seu app):",
                    value=url_padrao,
                )

                # Formatador seguro de parâmetro de URL
                param_seguro = urllib.parse.quote(formacao_sel.strip())
                url_aluno = f"{app_url_base.rstrip('/')}/?prova_id={param_seguro}"

                col_q1, col_q2 = st.columns([1, 2])
                with col_q1:
                    qr_bytes = gerar_qrcode(url_aluno)
                    st.image(
                        qr_bytes,
                        caption="Escaneie para responder a prova",
                        width=220,
                    )

                with col_q2:
                    st.markdown("**Link direto para teste do aluno:**")
                    st.code(url_aluno)
                    st.caption("💡 Se ao escanear der erro, verifique se a URL informada acima corresponde exatamente à URL pública onde seu aplicativo está rodando.")

                st.divider()
                st.markdown("### Questões Geradas:")
                for q in provas_cadastradas[formacao_sel]["questoes"]:
                    st.markdown(f"**{q['id']}. {q['pergunta']}**")
                    for opt in q["opcoes"]:
                        st.caption(f"- {opt}")
                    st.caption(f"**Resposta Correta:** {q['resposta_correta']}")
                    st.write("")

    with tab_resultados:
        df_res = carregar_resultados()
        if df_res.empty:
            st.info("Nenhum resultado registrado.")
        else:
            st.dataframe(df_res, use_container_width=True)
            excel_bytes = exportar_excel(df_res)
            st.download_button(
                label="📊 Baixar Resultados em Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
