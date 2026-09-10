from io import BytesIO
import pandas as pd
import streamlit as st


def converter_df_para_excel(df):
    """Converte um DataFrame do Pandas para um arquivo Excel em memória."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados_Alunos")
    processed_data = output.getvalue()
    return processed_data


# ---------------------------------------------------------
# PAINEL DO INSTRUTOR: ÁREA DE RELATÓRIOS E DOWNLOAD
# ---------------------------------------------------------
st.subheader("📥 Exportar Resultados das Avaliações")

if (
    "historico_ranking" in st.session_state
    and len(st.session_state["historico_ranking"]) > 0
):
    # Converte o histórico salvo na sessão para DataFrame
    df_resultados = pd.DataFrame(st.session_state["historico_ranking"])

    # Exibe uma prévia da tabela na tela
    st.dataframe(df_resultados, use_container_width=True)

    # Gera os bytes do arquivo Excel
    excel_data = converter_df_para_excel(df_resultados)

    # Botão de download
    st.download_button(
        label="📊 Baixar Relatório Completo em Excel (.xlsx)",
        data=excel_data,
        file_name="resultados_avaliacoes_alunos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
else:
    st.info("Nenhum resultado registrado até o momento para exportação.")
