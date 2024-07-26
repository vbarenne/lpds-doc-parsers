__author__ = ['Alvin Leung', 'Victoria Barenne']

import streamlit as st
from streamlit import session_state as ss
from streamlit_pdf_viewer import pdf_viewer
import pdfplumber
import pandas as pd
from pathlib import Path

from data_connector import base_connector, cio_connector, ciomonthly_connector, cmo_connector, equitydeepdive_connector, equityswitch_connector, equitytoppicks_connector, rf_connector, rw_connector, wire_connector

st.set_page_config(layout="wide")
st.title("PDF Text Parser Visualisation")

# Initialize session state variables for PDF
if 'pdf_ref' not in ss:
    ss.pdf_ref = None

document_type_list = {'Baer Insight Equity Research': equitydeepdive_connector.EquityDeepDiveConnector,
                        'Baer Insight Equity Research India': equitydeepdive_connector.EquityDeepDiveConnector,
                        'Equity Switch': equityswitch_connector.EquitySwitchConnector, # TODO download for testing
                        'Equity Top Picks': equitytoppicks_connector.EquityTopPicksConnector, # TODO download for testing
                        'Market Opportunity - Single Equities': cmo_connector.CMOConnector,
                        'Research Weekly': rw_connector.RWConnector,
                        'The Wire': wire_connector.WireConnector,
                        'CIO Weekly': cio_connector.CIOConnector, # TODO download for testing
                        'CIO Monthly': ciomonthly_connector.CIOMonthlyConnector # TODO download for testing
                        }

# Upload PDF file
connector_type = st.selectbox("Connector Type", options = document_type_list.keys())
connector = document_type_list[connector_type]
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf")

def create_dataframe_from_non_none_elements(data_dict_list):
    assert len(data_dict_list) > 0
    data_dict = data_dict_list[0]
    # Filter the dictionary to remove None values
    filtered_dict = {k: v for k, v in data_dict.items() if v is not None}
    # Create a DataFrame from the filtered dictionary
    df = pd.DataFrame(filtered_dict, index = ['Metadata'])
    to_keep = ["publication_date", "source_document", "series", "document_name"]
    return df[to_keep].T

if uploaded_file:
    ss.pdf_ref = uploaded_file  # backup

# Extract metadata and process the PDF if uploaded
if ss.pdf_ref:
    file_name = ss.pdf_ref.name
    doc_type = file_name.split('-')[0].split(' India')[0]
    binary_data = ss.pdf_ref.getvalue()  # Read binary data

    with st.spinner('Processing...'):
        # Save the uploaded file temporarily
        temp_path = Path(f"temp_{file_name}")
        with open(temp_path, "wb") as temp_file:
            temp_file.write(ss.pdf_ref.getbuffer())

    if connector_type == "Equity Top Picks":
        equity_extractions, deletions_table, metadata, equity_pages_no, deletion_pages_no = connector.get_all_components(str(temp_path))
        st.table(metadata)
        equity_counter, deletions_counter = 0, 0
        for page_nbr in range(1, len(binary_data)+1):
            if page_nbr in deletion_pages_no or page_nbr in equity_pages_no:
                col1, col2 = st.columns([3, 4])
                with col1: 
                    if page_nbr in deletion_pages_no:
                        st.table(deletions_table[deletions_counter])
                        deletions_counter +=1
                    elif page_nbr in equity_pages_no: 
                        title, key_info, investment_thesis, company_profile = equity_extractions[equity_counter]
                        equity_counter +=1
                        st.header(title)
                        st.table(key_info)
                        st.subheader("Company Profile")
                        st.write(company_profile)
                        st.subheader("Investment Thesis")
                        st.write(investment_thesis)     
                with col2:
                    binary_data = ss.pdf_ref.getvalue()  # Read binary data
                    pdf_viewer(input=binary_data, pages_to_render=[page_nbr], width=900)
    elif connector_type in ['Baer Insight Equity Research', 'Baer Insight Equity Research India']:
        equity_json, metadata, investment_thesis, company_profile, free_text, strengths, weaknesses, opportunities, threats = connector.get_all_components(str(temp_path))
        st.table(metadata)
        col1, col2 = st.columns([3, 4])
        with col1: 
            st.subheader("Company Profile")
            st.write(company_profile)
            st.subheader("Investment Thesis")
            st.write(investment_thesis)   
            st.subheader("Additional Text")
            st.write(free_text)     
            st.subheader("Equity Information")
            st.write(pd.json_normalize(equity_json).T)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[1], width=900)
        col1, col2 = st.columns([3, 4])
        with col1: 
            for key, text in {"Strengths": strengths, "Weaknesses": weaknesses, "Opportunities": opportunities, "Threats": threats}.items():
                st.subheader(key)
                st.write(text)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[2], width=900)

    elif connector_type == "Market Opportunity - Single Equities":
        equity_json, metadata, company_profile, market_opportunity, key_risks = connector.get_all_components(str(temp_path))
        st.table(metadata)
        col1, col2 = st.columns([3, 4])
        with col1: 
            st.subheader("Market Opportunity")
            st.write(market_opportunity)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[1], width=900)
        col1, col2 = st.columns([3, 4])
        with col1: 
            st.subheader("Company Profile")
            st.write(company_profile)
            st.subheader("Key Risks")
            st.write(key_risks)   
            st.subheader("Equity Information")
            st.write(pd.json_normalize(equity_json).T)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[2], width=900)
                
    elif connector_type == "Equity Switch":
        equity_json1, equity_json2, metadata, whats_the_story, header1, text1, header2, text2, comparaison_table = connector.get_all_components(str(temp_path))
        st.table(metadata)
        col1, col2 = st.columns([3, 4])
        with col1: 
            st.subheader("What's the Story")
            st.write(whats_the_story)
            st.subheader(header1)
            st.write(text1)
            st.subheader(header2)
            st.write(text2)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[1], width=900)
        col1, col2 = st.columns([3, 4])
        with col1: 
            st.subheader(f"Equity Information {equity_json1['equity']}")
            st.write(pd.json_normalize(equity_json1).T)  
            st.subheader(f"Equity Information {equity_json2['equity']}")
            st.write(pd.json_normalize(equity_json2).T)
        with col2:
            binary_data = ss.pdf_ref.getvalue()  # Read binary data
            pdf_viewer(input=binary_data, pages_to_render=[2], width=900)
            st.table(comparaison_table)

    
    
    else:
        outputs = connector.get_json_all(str(temp_path))

        # Filter and display outputs table
        st.table(create_dataframe_from_non_none_elements(outputs))
        
        # Iterate through the outputs and group by page number
        current_page = None
        sections = []

        for output in outputs:
            page_number = output['page_number']

            if current_page is None:
                current_page = page_number

            if page_number != current_page:
                # Display the previous page's content
                st.subheader(f"Page {current_page}")
                col1, col2 = st.columns([3, 4])
                with col1:
                    for section in sections:
                        st.write(section)
                with col2:
                    binary_data = ss.pdf_ref.getvalue()  # Read binary data
                    pdf_viewer(input=binary_data, pages_to_render=[current_page], width=900)

                # Reset for the new page
                current_page = page_number
                sections = []

            sections.append(output['section_text'])

        # Display the last page's content
        if sections:
            st.subheader(f"Page {current_page}")
            col1, col2 = st.columns([3, 4])
            with col1:
                for section in sections:
                    st.write(section)
            with col2:
                binary_data = ss.pdf_ref.getvalue()  # Read binary data
                pdf_viewer(input=binary_data, pages_to_render=[current_page], width=900)