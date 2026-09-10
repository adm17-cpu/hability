from datetime import datetime
from io import BytesIO
import json
import os
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
    initial_sidebar_state="expanded",
)

# Nomes dos arquivos de persistência local
ARQUIVO_PROVAS = "provas_bd.json"
ARQUIVO_RESULTADOS = "resultados_bd.csv"


# -----------------------------------------------------------------------------
# FUNÇÕES DE PERSISTÊNCIA DE DADOS (BANCO DE DADOS LOCAL)
# -----------------------------------------------------------------------------
def carregar_provas():
    """Carrega as provas salvas do arquivo JSON."""
    if os.path.exists(ARQUIVO_PROVAS):
        try:
            with open(ARQUIVO_PROVAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def salvar_prova(titulo_formacao, questoes):
    """Salva uma nova prova no arquivo JSON."""
    provas = carregar_provas()
    provas[titulo_formacao] = {
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "questoes": questoes,
    }
    with open(ARQUIVO_PROVAS, "w", encoding="utf-8") as f:
        json.dump(provas, f, ensure_ascii=False, indent=4)


def carregar_resultados():
    """Carrega o histórico de resultados do arquivo CSV."""
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
    """Adiciona um novo resultado ao arquivo CSV."""
    df_existente = carregar_resultados()
    df_novo = pd.DataFrame([novo_resultado_dict])
    df_atualizado = pd.concat([df_existente, df_novo], ignore_index=True)
    df_atualizado.to_csv(ARQUIVO_RESULTADOS, index=False, encoding="utf-8")


def gerar_qrcode(url):
    """Gera a imagem do QR Code a partir de uma URL."""
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


def exportar_excel(df_resultados):
    """Gera o arquivo Excel (.xlsx) formatado para download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Aba 1: Resultados Completos
        df_resultados.to_excel(
            writer, sheet_name="Resultados_Detalhados", index=False
        )

        # Aba 2: Ranking Geral por Formação
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
# ROTEAMENTO DA APLICAÇÃO (MODO ALUNO VS MODO PAINEL ADMIN)
# -----------------------------------------------------------------------------
params = st.query_params
prova_param = params.get("prova_id", None)

# Inicializar dicionário de provas na sessão
provas_cadastradas = carregar_provas()

if prova_param:
    # =========================================================================
    # MÓDULO DO ALUNO (ACESSO VIA QR CODE / LINK)
    # =========================================================================
    formacao_nome = prova_param

    st.header(f"📝 Avaliação de Conhecimento")
    st.subheader(f"Formação: **{formacao_nome}**")
    st.caption(
        "Responda às 5 questões abaixo. Cada questão vale 20 pontos (Total: 100 pontos)."
    )
    st.divider()

    if formacao_nome not in provas_cadastradas:
        st.error(
            "⚠️ A prova solicitada não foi encontrada ou ainda não foi criada pelo instrutor."
        )
        st.info("Verifique se leu o QR Code correto.")
    else:
        prova_data = provas_cadastradas[formacao_nome]
        questoes = prova_data["questoes"]

        # Formulário de Resposta
        with st.form(key="form_avaliacao_aluno"):
            st.markdown("### 👤 Dados de Identificação")
            col_a, col_b = st.columns(2)
            with col_a:
                nome = st.text_input("Nome:*", placeholder="Ex: João")
            with col_b:
                sobrenome = st.text_input(
                    "Sobrenome:*", placeholder="Ex: Silva"
                )

            unidade = st.text_input(
                "Curso / Unidade / Turma:*",
                placeholder="Ex: Unidade Centro - Turma A",
            )

            st.divider()
            st.markdown("### ❓ Questões da Prova")

            respostas_usuario = {}
            for idx, q in enumerate(questoes, 1):
                st.markdown(f"**Questão {idx}: {q['pergunta']}**")
                respostas_usuario[idx] = st.radio(
                    label=f"Selecione uma alternativa para a questão {idx}",
                    options=q["opcoes"],
                    key=f"q_{idx}",
                    index=None,
                    label_visibility="collapsed",
                )
                st.write("")

            bot_submeter = st.form_submit_button(
                "📥 Finalizar e Enviar Prova", type="primary", use_container_width=True
            )

        if bot_submeter:
            if not nome.strip() or not sobrenome.strip() or not unidade.strip():
                st.error(
                    "⚠️ Por favor, preencha todos os seus dados de identificação (Nome, Sobrenome e Unidade)."
                )
            elif None in respostas_usuario.values():
                st.error("⚠️ Por favor, responda a todas as 5 questões antes de enviar.")
            else:
                # Cálculo da pontuação
                acertos = 0
                detalhes_q = {}
                for idx, q in enumerate(questoes, 1):
                    resp_aluno = respostas_usuario[idx]
                    resp_correta = q["resposta_correta"]
                    is_correct = resp_aluno == resp_correta
                    if is_correct:
                        acertos += 1
                    detalhes_q[f"Q{idx}"] = (
                        f"{'Correct' if is_correct else 'Incorrect'} ({resp_aluno})"
                    )

                nota_final = acertos * 20
                nome_completo = f"{nome.strip().title()} {sobrenome.strip().title()}"

                # Salvar no CSV
                registro = {
                    "Data_Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Formacao": formacao_nome,
                    "Nome": nome.strip().title(),
                    "Sobrenome": sobrenome.strip().title(),
                    "Nome_Completo": nome_completo,
                    "Unidade": unidade.strip(),
                    "Nota": nota_final,
                    "Acertos": f"{acertos}/5",
                    "Q1": detalhes_q["Q1"],
                    "Q2": detalhes_q["Q2"],
                    "Q3": detalhes_q["Q3"],
                    "Q4": detalhes_q["Q4"],
                    "Q5": detalhes_q["Q5"],
                }
                salvar_resultado(registro)

                # Feedback e Animação
                st.balloons()
                st.success("🎉 Prova enviada com sucesso!")

                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Nota Final", f"{nota_final} / 100 pts")
                col_m2.metric("Acertos", f"{acertos} de 5")
                col_m3.metric(
                    "Aproveitamento",
                    f"{(nota_final/100)*100:.0f}%",
                )

                st.divider()

                # 🏆 RANKING DA FORMAÇÃO ESPECÍFICA
                st.markdown(f"### 🏆 Ranking da Formação: **{formacao_nome}**")

                df_todos = carregar_resultados()
                df_formacao = df_todos[
                    df_todos["Formacao"] == formacao_nome
                ].copy()

                if not df_formacao.empty:
                    # Ordenar por Nota decrescente e Data/Hora crescente (desempate por quem fez primeiro)
                    df_ranking = df_formacao.sort_values(
                        by=["Nota", "Data_Hora"], ascending=[False, True]
                    ).reset_index(drop=True)
                    df_ranking.index += 1  # Posição começa em 1

                    df_exibicao = df_ranking[
                        ["Nome_Completo", "Unidade", "Nota", "Acertos"]
                    ].rename(
                        columns={
                            "Nome_Completo": "Aluno",
                            "Unidade": "Curso / Unidade",
                            "Nota": "Pontuação",
                        }
                    )

                    st.dataframe(df_exibicao, use_container_width=True)

else:
    # =========================================================================
    # MÓDULO DO INSTRUTOR / PAINEL ADMINISTRATIVO
    # =========================================================================
    st.title("⚙️ Painel do Instrutor: Gestão de Avaliações")
    st.caption(
        "Crie provas com apoio de IA gratuita, gere QR Codes de acesso e exporte os resultados em Excel."
    )

    tab_criar, tab_provas, tab_resultados = st.tabs(
        [
            "➕ Criar Nova Prova",
            "📋 Provas Criadas & QR Code",
            "📊 Resultados, Ranking & Excel",
        ]
    )

    # -------------------------------------------------------------------------
    # ABA 1: CRIAR NOVA PROVA
    # -------------------------------------------------------------------------
    with tab_criar:
        st.subheader("1. Dados da Formação")
        nome_formacao_input = st.text_input(
            "Nome do Treinamento / Formação:",
            placeholder="Ex: Treinamento de Atendimento ao Cliente v1",
        )

        st.subheader("2. Gerar Questões via ChatGPT/Gemini (Grátis)")
        st.write(
            "Para não depender de chaves pagas de API, você pode colar seu resumo da aula no gerador abaixo, copiar o prompt e colar na sua IA de preferência (ChatGPT, Gemini Web, Claude, etc.):"
        )

        conteudo_treinamento = st.text_area(
            "Cole aqui o resumo/conteúdo da sua aula:",
            height=150,
            placeholder="Ex: O protocolo de atendimento exige saudação inicial em até 30 segundos, escuta ativa, confirmação do problema e encerramento com pesquisa de satisfação...",
        )

        prompt_modelo = f"""Com base no conteúdo de treinamento a seguir, crie exatamente 5 questões de múltipla escolha.
Cada questão deve ter exatamente 4 alternativas (A, B, C, D) e 1 resposta correta exata.

REGRAS OBRIGATÓRIAS:
- Retorne APENAS um JSON válido.
- Não adicione texto antes ou depois do JSON.
- As alternativas devem ser exatamente no formato: ["A) ...", "B) ...", "C) ...", "D) ..."]
- A resposta_correta deve ser IDÊNTICA a uma das opções do vetor.

Estrutura JSON exigida:
[
  {{
    "id": 1,
    "pergunta": "Pergunta 1 aqui?",
    "opcoes": ["A) Opção 1", "B) Opção 2", "C) Opção 3", "D) Opção 4"],
    "resposta_correta": "A) Opção 1"
  }}
]

CONTEÚDO BASE:
{conteudo_treinamento if conteudo_treinamento.strip() else '[INSIRA O CONTEÚDO AQUI]'}"""

        with st.expander("📋 Clique aqui para visualizar e copiar o Prompt para a IA"):
            st.code(prompt_modelo, language="markdown")

        st.subheader("3. Inserir o JSON de Questões Gerado")
        json_questoes_input = st.text_area(
            "Cole abaixo o JSON retornado pela IA:",
            height=220,
            placeholder='[\n  {\n    "id": 1,\n    "pergunta": "Qual é o tempo limite de saudação?",\n    "opcoes": ["A) 30s", "B) 1min", "C) 2min", "D) 5min"],\n    "resposta_correta": "A) 30s"\n  }\n]',
        )

        if st.button("💾 Salvar e Publicar Prova", type="primary"):
            if not nome_formacao_input.strip():
                st.error("⚠️ Insira o nome da formação.")
            elif not json_questoes_input.strip():
                st.error("⚠️ Cole o JSON com as 5 questões.")
            else:
                try:
                    questoes_parsed = json.loads(json_questoes_input.strip())
                    if not isinstance(questoes_parsed, list) or len(questoes_parsed) != 5:
                        st.error("⚠️ O JSON deve conter uma lista com exatamente 5 questões.")
                    else:
                        salvar_prova(nome_formacao_input.strip(), questoes_parsed)
                        st.success(f"✅ Prova para '{nome_formacao_input.strip()}' criada e salva com sucesso!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao ler o JSON: {str(e)}. Certifique-se de colar apenas a estrutura JSON válida.")

    # -------------------------------------------------------------------------
    # ABA 2: PROVAS CRIADAS & QR CODE
    # -------------------------------------------------------------------------
    with tab_provas:
        provas_atuais = carregar_provas()

        if not provas_atuais:
            st.info("Nenhuma prova foi cadastrada ainda. Utilize a aba 'Criar Nova Prova'.")
        else:
            st.subheader("Selecione uma Formação Cadastrada")
            formacao_sel = st.selectbox("Formação:", list(provas_atuais.keys()))

            if formacao_sel:
                st.divider()
                st.markdown(f"### 🔗 Link de Acesso e QR Code: **{formacao_sel}**")

                # URL base da sua aplicação (Substitua quando hospedar no Streamlit Cloud)
                app_url_base = st.text_input(
                    "URL Base da sua Aplicação (Streamlit Cloud):",
                    value="https://seu-app.streamlit.app",
                    help="Exemplo: https://minha-empresa-provas.streamlit.app",
                )

                # URL final para o aluno acessar
                url_aluno = f"{app_url_base.rstrip('/')}/?prova_id={formacao_sel.replace(' ', '%20')}"

                col_qr1, col_qr2 = st.columns([1, 2])

                with col_qr1:
                    qr_bytes = gerar_qrcode(url_aluno)
                    st.image(
                        qr_bytes,
                        caption="QR Code para projeção na tela",
                        width=220,
                    )

                with col_qr2:
                    st.markdown("**Copie e compartilhe o link direto:**")
                    st.code(url_aluno, language="text")
                    st.info(
                        "💡 **Dica de uso:** Projete este QR Code no slide final do seu treinamento. Os alunos escaneiam a câmera do celular, respondem a prova em 2 minutos e visualizam o ranking na tela instantaneamente."
                    )

                st.divider()
                st.markdown("### 🔍 Preview das Questões Cadastradas")
                for q in provas_atuais[formacao_sel]["questoes"]:
                    st.markdown(f"**{q['id']}. {q['pergunta']}**")
                    for opt in q["opcoes"]:
                        is_gabarito = opt == q["resposta_correta"]
                        st.caption(
                            f"{'✅ ' if is_gabarito else '⚪ '} {opt}"
                        )

    # -------------------------------------------------------------------------
    # ABA 3: RESULTADOS, RANKING & EXPORTAR EXCEL
    # -------------------------------------------------------------------------
    with tab_resultados:
        df_res = carregar_resultados()

        if df_res.empty:
            st.info("Nenhum aluno respondeu às provas ainda.")
        else:
            st.subheader("📈 Resumo Geral do Desempenho")

            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            col_stat1.metric("Total de Respostas", len(df_res))
            col_stat2.metric("Média Geral de Notas", f"{df_res['Nota'].mean():.1f} pts")
            col_stat3.metric("Maior Nota", f"{df_res['Nota'].max()} pts")
            
            aprovados = len(df_res[df_res["Nota"] >= 60])
            taxa_aprovacao = (aprovados / len(df_res)) * 100
            col_stat4.metric("Taxa de Aprovação (≥60)", f"{taxa_aprovacao:.1f}%")

            st.divider()

            # Filtro por Formação
            st.subheader("🏆 Ranking e Classificação por Formação")
            formacoes_disponiveis = ["Todas"] + list(df_res["Formacao"].unique())
            filtro_f = st.selectbox("Filtrar por Formação:", formacoes_disponiveis)

            if filtro_f != "Todas":
                df_exibir = df_res[df_res["Formacao"] == filtro_f]
            else:
                df_exibir = df_res

            st.dataframe(
                df_exibir[
                    [
                        "Data_Hora",
                        "Formacao",
                        "Nome_Completo",
                        "Unidade",
                        "Nota",
                        "Acertos",
                    ]
                ].sort_values(by="Nota", ascending=False),
                use_container_width=True,
            )

            st.divider()
            st.subheader("📥 Exportar Dados para Análise")

            excel_bytes = exportar_excel(df_res)

            st.download_button(
                label="📊 Baixar Planilha Completa em Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"relatorio_avaliacoes_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
