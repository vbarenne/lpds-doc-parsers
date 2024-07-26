import streamlit as st
from streamlit import session_state as ss
from streamlit_pdf_viewer import pdf_viewer
import pdfplumber
import pandas as pd
from pathlib import Path

from data_connector import base_connector, cio_connector, ciomonthly_connector, cmo_connector, equitydeepdive_connector, equityswitch_connector, equitytoppicks_connector, rf_connector, rw_connector, wire_connector

st.set_page_config(layout="wide")
    
def get_tables(df_name):
    storage = {}
    pdf = pdfplumber.open(df_name)
    
    for page in pdf.pages:
        tables = page.extract_tables(table_settings={"vertical_strategy": "text", 
                                                     "horizontal_strategy": "lines_strict",
                                                     "text_tolerance": 3, 
                                                     "snap_tolerance": 7,})

        for table in tables:
            if table[1:]:
                headers = table[0]
                body = table[1:]
                
                # Identify columns to drop or merge
                columns_to_drop = []
                columns_to_merge = []
                new_headers = []

                for i, header in enumerate(headers):
                    header_empty = len(header.strip()) < 3
                    column_body = [row[i] for row in body]
                    body_empty = all(str(cell).strip() == '' for cell in column_body)

                    if header_empty and body_empty:
                        columns_to_drop.append(i)
                    elif header_empty and not body_empty:
                        if new_headers:
                            new_headers[-1] += header
                        columns_to_merge.append(i)
                    elif not header_empty and body_empty:
                        if new_headers:
                            new_headers[-1] += header
                        columns_to_drop.append(i)
                    else:
                        new_headers.append(header)

                new_body = []
                for row in body:
                    new_row = []
                    for j, cell in enumerate(row):
                        if j not in columns_to_drop and j not in columns_to_merge:
                            new_row.append(cell)
                    if columns_to_merge:
                        merged_value = ' '.join(str(row[j]).strip() for j in columns_to_merge)
                        new_row.append(merged_value)
                    new_body.append(new_row)
                
                # Create DataFrame with the new headers and body
                if new_body and new_headers:
                    print(new_headers)
                    if len(new_headers) + 1 == len(new_body[0]):
                        newer_headers = ['_',].extend(new_headers)
                        found_table = pd.DataFrame(new_body, columns=newer_headers)
                    else:
                        found_table = pd.DataFrame(new_body, columns=new_headers)
                    # Store the found table
                    if page.page_number not in storage.keys():
                        storage[page.page_number] = [found_table]
                    else:
                        storage[page.page_number].append(found_table)

    return storage

st.title("PDF Text Parser Visualisation")

# Initialize session state variables for PDF
if 'pdf_ref' not in ss:
    ss.pdf_ref = None

# Upload PDF file
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf")

document_type_list = {'Baer Insight Equity Research': equitydeepdive_connector.EquityDeepDiveConnector,
                        'Baer Insight Equity Research India': equitydeepdive_connector.EquityDeepDiveConnector,
                        'Equity Switch': equityswitch_connector.EquitySwitchConnector, # TODO download for testing
                        'Equity Top Picks': equitytoppicks_connector.EquityTopPicksConnector, # TODO download for testing
                        'Baer Insight Fixed Income Research': None, #TODO: Build Connector
                        'Baseline Scenario': None, #TODO: Build Connector
                        'Commodity Fact Sheet': None, #TODO: Build Connector
                        'Digital Asset Fact Sheet': None, #TODO: Build Connector
                        'Economic Calendar': None, #TODO: Build Connector
                        'Investment View (Global)': None, #TODO: Build Connector
                        'Market Opportunity - Single Equities': cmo_connector.CMOConnector,
                        'Market Opportunity - Structured Products': cmo_connector.BaseConnector,
                        'Next Generation (Global)': None, #TODO: Build Connector
                        'Research Focus': rf_connector.RFConnector,
                        'Research Weekly': rw_connector.RWConnector,
                        'Technical Investment Strategy': None, #TODO: Build Connector
                        'The Wire': wire_connector.WireConnector,
                        'Viewpoints': None, #TODO: Build Connector
                        'CIO Weekly': cio_connector.CIOConnector, # TODO download for testing
                        'CIO Monthly': ciomonthly_connector.CIOMonthlyConnector # TODO download for testing
                        }

def get_connector(file_name, document_type_list):
    doc_type = file_name.split('-')[0]
    if doc_type in document_type_list.keys():
        connector = document_type_list[file_name.split('-')[0]]
    else:
        connector = base_connector.BaseConnector
    return connector

def create_dataframe_from_non_none_elements(data_dict_list):
    assert len(data_dict_list) > 0
    data_dict = data_dict_list[0]
    # Filter the dictionary to remove None values
    filtered_dict = {k: v for k, v in data_dict.items() if v is not None}
    # Create a DataFrame from the filtered dictionary
    df = pd.DataFrame(filtered_dict, index = ['Metadata'])
    to_keep = list(df.columns)[0:3]
    return df[to_keep].T

if uploaded_file:
    ss.pdf_ref = uploaded_file  # backup
    #tables = get_tables(ss.pdf_ref)

# Extract metadata and process the PDF if uploaded
if ss.pdf_ref:
    file_name = ss.pdf_ref.name
    doc_type = file_name.split('-')[0].split(' India')[0]
    connector = get_connector(file_name, document_type_list)
    with st.spinner('Processing...'):
        # Save the uploaded file temporarily
        temp_path = Path(f"temp_{file_name}")
        with open(temp_path, "wb") as temp_file:
            temp_file.write(ss.pdf_ref.getbuffer())
    outputs = connector.get_json_all(str(temp_path))

    if doc_type == 'Baer Insight Equity Research':
        investment_thesis = outputs['investment_thesis']
        additional_information = outputs['additional_information']
        company_profile = outputs['company_profile']
        strengths = outputs['strengths']
        weaknesses = outputs['weaknesses']
        opportunities = outputs['opportunities']
        threats = outputs['threats']
        metadata = pd.DataFrame({keys: outputs[keys] for keys in ['document_type', 'document_name', 'publication_date', 'equity', 'industries', 'country', 'rating']}, index=['Metadata']).T
        st.table(metadata)
        for page in range(1, 3):
            col1, col2 = st.columns([3, 4])
            if page == 1:
                with col1:
                    st.subheader("Investment Thesis")
                    st.write(investment_thesis)
                    st.subheader("Additional Information")
                    st.write(additional_information)
                    st.subheader("Company Profile")
                    st.write(company_profile)

                with col2:
                    # Display the PDF page
                    binary_data = ss.pdf_ref.getvalue()  # Read binary data
                    pdf_viewer(input=binary_data, pages_to_render=[page], width=900)
            else:
                st.write('---')
                with col1:
                    st.subheader("Strengths")
                    st.write(strengths)
                    st.subheader("Weaknesses")
                    st.write(weaknesses)
                    st.subheader("Opportunities")
                    st.write(opportunities)
                    st.subheader("Threats")
                    st.write(threats)
                with col2:
                    # Display the PDF page
                    binary_data = ss.pdf_ref.getvalue()  # Read binary data
                    pdf_viewer(input=binary_data, pages_to_render=[page], width=900)
    else:
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
